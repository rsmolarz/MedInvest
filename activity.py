"""Centralized activity logging for analytics."""
from datetime import datetime
from app import db
from models import UserActivity


def log_activity(user_id: int, activity_type: str, entity_type: str = None, entity_id: int = None):
    """Log a user activity event.
    
    Args:
        user_id: The ID of the user performing the action
        activity_type: Type of activity (view, post, comment, endorse, deal_create, ai_run, invite_accept, etc.)
        entity_type: Optional type of entity (deal, post, comment, digest, invite)
        entity_id: Optional ID of the related entity
    """
    try:
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=datetime.utcnow()
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging activity: {e}")


def log_verification_submit(user_id: int):
    """Log verification submission."""
    log_activity(user_id, 'verification_submit', 'verification', user_id)


def log_verification_approve(user_id: int, admin_id: int):
    """Log verification approval."""
    log_activity(admin_id, 'verification_approve', 'verification', user_id)


def log_verification_reject(user_id: int, admin_id: int):
    """Log verification rejection."""
    log_activity(admin_id, 'verification_reject', 'verification', user_id)


def log_deal_create(user_id: int, deal_id: int):
    """Log deal creation."""
    log_activity(user_id, 'deal_create', 'deal', deal_id)


def log_deal_view(user_id: int, deal_id: int):
    """Log deal view."""
    log_activity(user_id, 'deal_view', 'deal', deal_id)


def log_ai_job_enqueue(user_id: int, job_id: int):
    """Log AI job enqueue."""
    log_activity(user_id, 'ai_run', 'ai_job', job_id)


def log_invite_create(user_id: int, invite_id: int):
    """Log invite creation."""
    log_activity(user_id, 'invite_create', 'invite', invite_id)


def log_invite_accept(user_id: int, invite_id: int):
    """Log invite acceptance."""
    log_activity(user_id, 'invite_accept', 'invite', invite_id)


def log_outcome_submit(user_id: int, deal_id: int):
    """Log deal outcome submission."""
    log_activity(user_id, 'outcome_submit', 'deal', deal_id)


def log_report_submit(user_id: int, report_id: int):
    """Log content report submission."""
    log_activity(user_id, 'report_submit', 'report', report_id)


def log_post_create(user_id: int, post_id: int):
    """Log post creation."""
    log_activity(user_id, 'post', 'post', post_id)


def log_comment_create(user_id: int, comment_id: int):
    """Log comment creation."""
    log_activity(user_id, 'comment', 'comment', comment_id)


def log_endorse(user_id: int, post_id: int):
    """Log post endorsement."""
    log_activity(user_id, 'endorse', 'post', post_id)
