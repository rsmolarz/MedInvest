from __future__ import annotations

import json
from typing import Any, Optional

from app import db
from models import ReputationEvent, User


# Canonical event weights. Adjust as your community matures.
EVENT_WEIGHTS = {
    "post_created": 2,
    "comment_created": 1,
    "post_endorsed": 3,
    "comment_endorsed": 2,
    "deal_post_created": 5,
    "moderation_penalty": -10,
}


def record_reputation_event(
    *,
    user: User,
    event_type: str,
    weight: Optional[int] = None,
    related_post_id: Optional[int] = None,
    related_group_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> ReputationEvent:
    """Append-only reputation event stream + cached score update."""
    if weight is None:
        weight = int(EVENT_WEIGHTS.get(event_type, 0))

    ev = ReputationEvent(
        user_id=user.id,
        event_type=event_type,
        weight=weight,
        related_post_id=related_post_id,
        related_group_id=related_group_id,
        meta_json=json.dumps(meta or {}) if meta is not None else None,
    )
    db.session.add(ev)

    # Update cached score (fast read path)
    user.reputation_score = int(user.reputation_score or 0) + int(weight)
    db.session.add(user)
    return ev
