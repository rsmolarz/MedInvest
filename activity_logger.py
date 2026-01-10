"""Lightweight activity logging for accurate WAU/DAU and cohort analytics.

Usage:
    from activity_logger import log_activity
    log_activity(db, user.id, 'post', 'post', post.id)
"""
from __future__ import annotations
import logging
from typing import Optional

from app import db
from models import UserActivity


def log_activity(
    user_id: int,
    activity_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> None:
    """Log a user activity. Non-blocking; failures are logged but never raise."""
    try:
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log activity: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
