"""Auto-moderation engine.

This is intentionally simple (MLP):
- Uses reputation_score, report velocity, and prior moderation history.
- Applies actions via flags on Post/Comment (hide/lock/downrank).
- Records ModerationEvent for auditability.

All thresholds are tweakable via CohortNorm. If no cohort norm exists, defaults apply.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Optional, Tuple

from app import db
from models import (
    User,
    Post,
    Comment,
    ContentReport,
    CohortNorm,
    ModerationEvent,
)

EntityType = Literal["post", "comment"]


def _get_cohort_norm(user: User) -> CohortNorm:
    # Prefer specialty; fallback to role; else defaults.
    n = None
    if user.specialty:
        n = CohortNorm.query.filter_by(cohort_dimension="specialty", cohort_value=user.specialty).first()
    if n is None and user.role:
        n = CohortNorm.query.filter_by(cohort_dimension="role", cohort_value=user.role).first()
    if n is None:
        # Defaults aligned with earlier discussion.
        n = CohortNorm(
            cohort_dimension="specialty",
            cohort_value="*",
            min_reputation_to_post=0,
            max_reports_before_hide=3,
            auto_lock_threshold=-5.0,
        )
    return n


def compute_signal_score(
    *,
    author: User,
    entity_type: EntityType,
    entity_id: int,
) -> Tuple[float, dict]:
    """Return (signal_score, breakdown)."""

    now = datetime.utcnow()
    window_start = now - timedelta(hours=24)

    # Reports
    reports_24h = ContentReport.query.filter(
        ContentReport.entity_type == entity_type,
        ContentReport.entity_id == entity_id,
        ContentReport.created_at >= window_start,
    ).count()

    reports_total = ContentReport.query.filter_by(entity_type=entity_type, entity_id=entity_id).count()

    # Prior moderation history for this author
    prior_mod_hits_90d = ModerationEvent.query.filter(
        ModerationEvent.user_id == author.id,
        ModerationEvent.created_at >= (now - timedelta(days=90)),
        ModerationEvent.action.in_(["hide", "lock", "review"]),
    ).count()

    # Reputation buffer (log1p-ish without importing math)
    rep = max(int(author.reputation_score or 0), 0)
    rep_term = 0.0
    if rep > 0:
        # piecewise approx to log1p
        rep_term = 1.0 + (rep ** 0.5) / 5.0

    # Core score
    score = 0.0
    score += rep_term
    score -= reports_total * 3.0
    score -= reports_24h * 1.5
    score -= prior_mod_hits_90d * 2.0

    breakdown = {
        "rep": rep,
        "rep_term": rep_term,
        "reports_total": reports_total,
        "reports_24h": reports_24h,
        "prior_mod_hits_90d": prior_mod_hits_90d,
    }
    return score, breakdown


def decide_action(*, score: float, norm: CohortNorm, reports_total: int) -> str:
    # Report-based hard hide
    if reports_total >= int(norm.max_reports_before_hide or 3):
        return "hide"

    # Score-based actions
    if score > 5:
        return "none"  # allow + boost handled by ranking, not flags
    if 0 <= score <= 5:
        return "none"
    if -2 <= score < 0:
        return "downrank"
    if -5 <= score < -2:
        return "hide"
    if score < float(norm.auto_lock_threshold or -5.0):
        return "lock"
    return "review"


def apply_moderation(
    *,
    entity_type: EntityType,
    entity_id: int,
    reason: str,
) -> Optional[ModerationEvent]:
    """Compute moderation signal and apply flags.

    Returns ModerationEvent if any action other than 'none' is taken.
    """

    author_id = None
    entity = None
    if entity_type == "post":
        entity = Post.query.get(entity_id)
        if not entity:
            return None
        author_id = entity.author_id
    else:
        entity = Comment.query.get(entity_id)
        if not entity:
            return None
        author_id = entity.author_id

    author = User.query.get(author_id)
    if not author:
        return None

    norm = _get_cohort_norm(author)

    score, breakdown = compute_signal_score(author=author, entity_type=entity_type, entity_id=entity_id)
    reports_total = int(breakdown.get("reports_total") or 0)
    action = decide_action(score=score, norm=norm, reports_total=reports_total)

    # Apply flags
    if action == "downrank":
        entity.downrank_score = float(entity.downrank_score or 0.0) + 1.0
    elif action == "hide":
        entity.is_hidden = True
    elif action == "lock":
        entity.is_locked = True
        entity.is_hidden = True

    if action == "none":
        return None

    ev = ModerationEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=author.id,
        signal_score=score,
        action=action,
        reason=f"{reason}; breakdown={breakdown}",
    )
    db.session.add(ev)
    return ev
