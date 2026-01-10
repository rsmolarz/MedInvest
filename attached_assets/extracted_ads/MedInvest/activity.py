"""User activity logging.

Call `log_activity()` from route handlers after successful actions.

Fail-open:
- Never raises.
- Uses caller transaction; do not commit here.
"""

from __future__ import annotations

import logging
from typing import Optional

from app import db
from models import UserActivity

logger = logging.getLogger(__name__)


def log_activity(
    *,
    user_id: int,
    activity_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> None:
    try:
        db.session.add(
            UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
    except Exception:
        logger.exception(
            "Failed to log activity: user_id=%s activity_type=%s entity_type=%s entity_id=%s",
            user_id,
            activity_type,
            entity_type,
            entity_id,
        )
