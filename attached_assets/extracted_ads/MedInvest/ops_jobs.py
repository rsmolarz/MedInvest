"""Operational background jobs.

Run them via `python scheduler.py` (simple loop) or import and call manually.

Jobs included:
- Verification SLA monitor (emails admin when breached)
- Auto-route verification queue when SLA breached
- Invite credit boosts based on activation by specialty
- Weekly digest generation (retention)
"""

from __future__ import annotations

from datetime import datetime, timedelta
import os

from app import app, db
from models import (
    User,
    VerificationQueueEntry,
    InviteCreditEvent,
    CohortNorm,
    Invite,
    Digest,
    DigestItem,
)
from mailer import send_email


def _hours(td) -> float:
    return float(td.total_seconds() / 3600.0)


def monitor_verification_sla_and_alert(*, sla_hours_threshold: float = 72.0) -> dict:
    """If p95 SLA for last 7d exceeds threshold, email admins."""
    now = datetime.utcnow()
    since_7d = now - timedelta(days=7)
    verified_recent = User.query.filter(User.verified_at >= since_7d).all()
    sla_hours = []
    for u in verified_recent:
        if u.verification_submitted_at and u.verified_at:
            sla_hours.append(_hours(u.verified_at - u.verification_submitted_at))
    sla_hours.sort()
    def pct(arr, p):
        if not arr:
            return None
        idx = max(0, min(len(arr)-1, int(round((p/100.0)*(len(arr)-1)))))
        return float(arr[idx])
    p95 = pct(sla_hours, 95)
    p50 = pct(sla_hours, 50)

    breached = (p95 is not None and p95 > sla_hours_threshold)

    if breached:
        # email all admins
        admins = User.query.filter(User.role == 'admin').all()
        to_emails = [a.email for a in admins if a.email]
        if to_emails:
            subject = f"[MedInvest] Verification SLA breached (p95={p95:.1f}h > {sla_hours_threshold:.1f}h)"
            body = (
                f"Verification SLA breach detected\n\n"
                f"Window: last 7 days\n"
                f"p50: {p50 if p50 is not None else 'n/a'} hours\n"
                f"p95: {p95 if p95 is not None else 'n/a'} hours\n\n"
                f"Recommended actions:\n"
                f"- Route the verification queue to reviewers\n"
                f"- Add reviewer coverage\n"
            )
            send_email(to_emails=to_emails, subject=subject, text=body)

    return {'p50_hours': p50, 'p95_hours': p95, 'breached': breached}


def auto_route_verification_queue(*, max_assign: int = 25) -> dict:
    """Assign oldest pending verification queue items to available reviewers."""
    now = datetime.utcnow()

    reviewers = User.query.filter(User.can_review_verifications == True).all()
    if not reviewers:
        # fallback: admins are reviewers
        reviewers = User.query.filter(User.role == 'admin').all()

    pending = VerificationQueueEntry.query.filter(VerificationQueueEntry.status == 'pending').order_by(VerificationQueueEntry.created_at.asc()).limit(max_assign).all()

    assigned = 0
    for idx, entry in enumerate(pending):
        reviewer = reviewers[idx % len(reviewers)] if reviewers else None
        if not reviewer:
            break
        entry.status = 'assigned'
        entry.assigned_reviewer_id = reviewer.id
        entry.assigned_at = now
        assigned += 1

    db.session.commit()
    return {'assigned': assigned}


def invite_credit_boosts_by_specialty(*, window_days: int = 30, min_activation_rate: float = 0.35, boost_credits: int = 1) -> dict:
    """Give additional invite credits to specialties with strong activation, encouraging quality growth.

    This is conservative: it only creates a CohortNorm marker + logs an InviteCreditEvent per user.
    """
    now = datetime.utcnow()
    since = now - timedelta(days=window_days)

    # Activated = created a deal OR requested ai_deal_analyze in window.
    activated = set(
        r[0] for r in db.session.execute(
            db.text(
                """
                SELECT DISTINCT user_id
                FROM user_activity
                WHERE created_at >= :since
                  AND activity_type IN ('deal_create','ai_deal_analyze')
                """
            ),
            {'since': since}
        ).fetchall()
    )

    users = User.query.filter(User.verification_status == 'verified').all()
    by_spec = {}
    for u in users:
        spec = (u.specialty or 'Unknown').strip() or 'Unknown'
        by_spec.setdefault(spec, {'users': [], 'activated': 0})
        by_spec[spec]['users'].append(u)
        if u.id in activated:
            by_spec[spec]['activated'] += 1

    boosted = 0
    for spec, bucket in by_spec.items():
        total = len(bucket['users'])
        act = bucket['activated']
        rate = (act / total) if total else 0.0
        if rate < min_activation_rate:
            continue

        # CohortNorm marker (optional)
        norm = CohortNorm.query.filter_by(cohort_dimension='specialty', cohort_value=spec).first()
        if not norm:
            norm = CohortNorm(cohort_dimension='specialty', cohort_value=spec)
            db.session.add(norm)

        for u in bucket['users']:
            if u.id not in activated:
                continue
            # prevent repeated boosts in same window
            exists = InviteCreditEvent.query.filter_by(user_id=u.id, reason='specialty_activation_boost').order_by(InviteCreditEvent.created_at.desc()).first()
            if exists and exists.created_at and exists.created_at >= since:
                continue
            u.invite_credits = int(u.invite_credits or 0) + int(boost_credits)
            db.session.add(InviteCreditEvent(user_id=u.id, delta=int(boost_credits), reason='specialty_activation_boost', cohort_dimension='specialty', cohort_value=spec))
            boosted += 1

    db.session.commit()
    return {'boosted_users': boosted}


def weekly_signal_digest() -> dict:
    """Generate a weekly digest stub.

    The app already includes digest generation logic. This job only creates an empty digest row
    if one doesn't exist for the current ISO week.
    """
    now = datetime.utcnow()
    year, week, _ = now.isocalendar()
    week_key = f"{year}-W{week:02d}"

    existing = Digest.query.filter_by(week_start=week_key).first()
    if existing:
        return {'created': False, 'week_key': week_key, 'digest_id': existing.id}

    d = Digest(week_start=week_key)
    db.session.add(d)
    db.session.commit()
    return {'created': True, 'week_key': week_key, 'digest_id': d.id}


def run_all_ops_jobs() -> dict:
    """Convenience function."""
    results = {}
    results['sla'] = monitor_verification_sla_and_alert(sla_hours_threshold=float(os.getenv('SLA_HOURS_THRESHOLD', '72')))
    if results['sla'].get('breached'):
        results['route'] = auto_route_verification_queue()
    results['invite_boosts'] = invite_credit_boosts_by_specialty()
    results['digest'] = weekly_signal_digest()
    return results
