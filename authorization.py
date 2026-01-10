"""Centralized authorization policy.

Single place to answer: "Can this user do this action on this resource?"

Design goals:
- Keep route handlers thin (no scattered permission logic).
- Return *both* allow/deny and a machine-readable reason.
- Be conservative by default (deny when uncertain).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


class Actions:
    # Generic
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MODERATE = "moderate"

    # Platform-specific
    ACCESS_PHYSICIAN_AREA = "access_physician_area"
    SUBMIT_VERIFICATION = "submit_verification"
    REVIEW_VERIFICATION = "review_verification"  # approve/reject
    ADMIN_REVIEW_VERIFICATION = "admin_review_verification"  # list pending, approve/reject

    VIEW_POST = "view_post"
    CREATE_POST = "create_post"
    COMMENT = "comment"
    REACT = "react"

    VIEW_GROUP = "view_group"
    JOIN_GROUP = "join_group"
    CREATE_GROUP = "create_group"

    SEND_DM = "send_dm"


def is_authenticated(user: Any) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def is_verified(user: Any) -> bool:
    # Support legacy boolean and new status.
    return bool(getattr(user, "is_verified", False)) or getattr(user, "verification_status", "unverified") == "verified"


def role(user: Any) -> str:
    return getattr(user, "role", "physician") or "physician"


def _has_role(user: Any, allowed_roles: set[str]) -> bool:
    r = role(user)
    return r == "admin" or r in allowed_roles


def can(user: Any, action: str, resource: Optional[Any] = None, **ctx: Any) -> Decision:
    """Authorization decision.

    Args:
        user: flask_login current_user-like object.
        action: one of Actions.*
        resource: optional model instance (Post, Group, etc.)
        ctx: optional context (e.g., required_roles=set(...), group_member=True)
    """

    if not is_authenticated(user):
        return Decision(False, "authentication_required")

    # Admin override for most actions (except where explicitly blocked).
    if role(user) == "admin":
        return Decision(True, "admin")

    # Role-gated actions
    required_roles = ctx.get("required_roles")
    if required_roles is not None:
        if not _has_role(user, set(required_roles)):
            return Decision(False, "forbidden_role")

    # Verification-gated actions
    if action in {
        Actions.ACCESS_PHYSICIAN_AREA,
        Actions.CREATE_POST,
        Actions.COMMENT,
        Actions.REACT,
        Actions.SEND_DM,
        Actions.CREATE_GROUP,
        Actions.JOIN_GROUP,
        Actions.VIEW_GROUP,
    }:
        if not is_verified(user):
            return Decision(False, "verification_required")

    # Resource-specific policies
    if action == Actions.VIEW_POST and resource is not None:
        visibility = getattr(resource, "visibility", "physicians")
        if visibility == "public":
            return Decision(True, "public")
        if visibility == "physicians":
            return Decision(True, "verified") if is_verified(user) else Decision(False, "verification_required")
        if visibility == "group":
            # Allow author to view regardless; otherwise require group membership.
            if getattr(resource, "author_id", None) == getattr(user, "id", None):
                return Decision(True, "author")
            is_member = bool(ctx.get("is_group_member", False))
            return Decision(True, "group_member") if is_member else Decision(False, "group_membership_required")
        return Decision(False, "unknown_visibility")

    if action in {Actions.SUBMIT_VERIFICATION}:
        # Any authenticated user may submit verification.
        return Decision(True, "ok")

    if action in {Actions.REVIEW_VERIFICATION, Actions.ADMIN_REVIEW_VERIFICATION, Actions.MODERATE}:
        # Non-admin needs explicit roles.
        if _has_role(user, {"admin"}):
            return Decision(True, "ok")
        return Decision(False, "forbidden")

    # Default allow for generic actions already gated above.
    return Decision(True, "ok")


def deny_response(reason: str) -> Tuple[dict, int]:
    """Map deny reasons to HTTP responses."""
    if reason == "authentication_required":
        return {"error": reason}, 401
    if reason in {"verification_required", "group_membership_required"}:
        return {"error": reason}, 403
    if reason in {"forbidden_role", "forbidden"}:
        return {"error": "forbidden", "reason": reason}, 403
    return {"error": "forbidden", "reason": reason}, 403
