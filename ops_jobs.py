"""Operational background jobs for SLA monitoring, routing, and notifications."""
import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import func

logger = logging.getLogger(__name__)


def monitor_verification_sla_and_alert():
    """Monitor verification queue and alert on SLA breaches."""
    from app import db
    from models import VerificationQueueEntry, Alert
    from mailer import send_verification_sla_alert
    
    # Calculate p50 and p95 wait times for pending verifications
    now = datetime.utcnow()
    pending = VerificationQueueEntry.query.filter(
        VerificationQueueEntry.status == 'pending'
    ).all()
    
    if not pending:
        logger.info("No pending verifications")
        return
    
    wait_times = [(now - p.submitted_at).total_seconds() / 3600 for p in pending]
    wait_times.sort()
    
    n = len(wait_times)
    p50 = wait_times[n // 2] if n > 0 else 0
    p95 = wait_times[int(n * 0.95)] if n > 0 else 0
    
    # Thresholds (configurable)
    p50_threshold = float(os.environ.get('VERIFICATION_SLA_P50_HOURS', '24'))
    p95_threshold = float(os.environ.get('VERIFICATION_SLA_P95_HOURS', '72'))
    
    window_start = now - timedelta(hours=1)
    
    # Check p50 breach
    if p50 > p50_threshold:
        # Check if we already alerted in the last hour
        recent_alert = Alert.query.filter(
            Alert.alert_type == 'verification_sla',
            Alert.metric == 'p50',
            Alert.created_at >= window_start
        ).first()
        
        if not recent_alert:
            alert = Alert(
                alert_type='verification_sla',
                metric='p50',
                value_hours=p50,
                threshold_hours=p50_threshold,
                window_start=window_start,
                window_end=now
            )
            db.session.add(alert)
            db.session.commit()
            
            send_verification_sla_alert('p50', p50, p50_threshold)
            alert.sent_at = datetime.utcnow()
            db.session.commit()
            logger.warning(f"Verification SLA p50 breach: {p50:.1f}h > {p50_threshold}h")
    
    # Check p95 breach
    if p95 > p95_threshold:
        recent_alert = Alert.query.filter(
            Alert.alert_type == 'verification_sla',
            Alert.metric == 'p95',
            Alert.created_at >= window_start
        ).first()
        
        if not recent_alert:
            alert = Alert(
                alert_type='verification_sla',
                metric='p95',
                value_hours=p95,
                threshold_hours=p95_threshold,
                window_start=window_start,
                window_end=now
            )
            db.session.add(alert)
            db.session.commit()
            
            send_verification_sla_alert('p95', p95, p95_threshold)
            alert.sent_at = datetime.utcnow()
            db.session.commit()
            logger.warning(f"Verification SLA p95 breach: {p95:.1f}h > {p95_threshold}h")


def auto_route_verification_queue():
    """Auto-assign verification requests to available reviewers."""
    from app import db
    from models import User, VerificationQueueEntry
    
    # Get unassigned pending verifications
    unassigned = VerificationQueueEntry.query.filter(
        VerificationQueueEntry.status == 'pending',
        VerificationQueueEntry.assigned_to_id.is_(None)
    ).order_by(VerificationQueueEntry.submitted_at).all()
    
    if not unassigned:
        return
    
    # Get available reviewers (admins who can review verifications)
    reviewers = User.query.filter(
        User.can_review_verifications == True,
        User.account_active == True
    ).all()
    
    if not reviewers:
        logger.warning("No verification reviewers available")
        return
    
    # Count current assignments per reviewer
    assignments = {}
    for reviewer in reviewers:
        count = VerificationQueueEntry.query.filter(
            VerificationQueueEntry.assigned_to_id == reviewer.id,
            VerificationQueueEntry.status.in_(['pending', 'in_review'])
        ).count()
        assignments[reviewer.id] = count
    
    # Assign unassigned to reviewer with fewest assignments
    for entry in unassigned:
        min_reviewer = min(reviewers, key=lambda r: assignments.get(r.id, 0))
        entry.assigned_to_id = min_reviewer.id
        entry.assigned_at = datetime.utcnow()
        assignments[min_reviewer.id] = assignments.get(min_reviewer.id, 0) + 1
    
    db.session.commit()
    logger.info(f"Auto-routed {len(unassigned)} verification requests")


def invite_credit_boosts_by_specialty():
    """Grant bonus invite credits based on specialty needs."""
    from app import db
    from models import User, InviteCreditEvent
    
    # Specialties we want to grow
    priority_specialties = os.environ.get('PRIORITY_SPECIALTIES', 'Cardiology,Oncology,Radiology').split(',')
    priority_specialties = [s.strip() for s in priority_specialties]
    
    # Find verified users in priority specialties with low invite credits
    users = User.query.filter(
        User.is_verified == True,
        User.specialty.in_(priority_specialties),
        User.invite_credits < 3
    ).all()
    
    boost_amount = 2
    
    for user in users:
        # Check if already boosted this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_boost = InviteCreditEvent.query.filter(
            InviteCreditEvent.user_id == user.id,
            InviteCreditEvent.reason == 'specialty_boost',
            InviteCreditEvent.created_at >= week_ago
        ).first()
        
        if not recent_boost:
            user.invite_credits += boost_amount
            event = InviteCreditEvent(
                user_id=user.id,
                delta=boost_amount,
                reason='specialty_boost'
            )
            db.session.add(event)
    
    db.session.commit()
    logger.info(f"Boosted invite credits for {len(users)} priority specialty users")


def weekly_signal_digest():
    """Send weekly digest emails to active users."""
    from app import db
    from models import User, Post, InvestmentDeal, ExpertAMA
    from mailer import send_weekly_digest
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    # Calculate stats
    new_posts = Post.query.filter(Post.created_at >= week_ago).count()
    new_deals = InvestmentDeal.query.filter(InvestmentDeal.created_at >= week_ago).count()
    upcoming_amas = ExpertAMA.query.filter(
        ExpertAMA.scheduled_for >= datetime.utcnow(),
        ExpertAMA.status == 'scheduled'
    ).count()
    
    stats = {
        'new_posts': new_posts,
        'new_deals': new_deals,
        'upcoming_amas': upcoming_amas
    }
    
    # Find active users (logged in within last 30 days)
    month_ago = datetime.utcnow() - timedelta(days=30)
    active_users = User.query.filter(
        User.last_seen >= month_ago,
        User.is_verified == True
    ).all()
    
    sent_count = 0
    for user in active_users:
        if send_weekly_digest(user.email, user.first_name, stats):
            sent_count += 1
    
    logger.info(f"Sent weekly digest to {sent_count} users")


def run_all_ops_jobs():
    """Run all operational jobs."""
    logger.info("Starting ops jobs run")
    
    try:
        monitor_verification_sla_and_alert()
    except Exception as e:
        logger.error(f"Error in monitor_verification_sla: {e}")
    
    try:
        auto_route_verification_queue()
    except Exception as e:
        logger.error(f"Error in auto_route_verification: {e}")
    
    try:
        invite_credit_boosts_by_specialty()
    except Exception as e:
        logger.error(f"Error in invite_credit_boosts: {e}")
    
    logger.info("Completed ops jobs run")
