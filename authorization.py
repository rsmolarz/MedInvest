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

    # Analytics & Reports
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_ANALYTICS = "export_analytics"
    VIEW_REPORTS = "view_reports"
    RESOLVE_REPORT = "resolve_report"
    SUBMIT_REPORT = "submit_report"

    # Sponsors
    SUBMIT_SPONSOR_PROFILE = "submit_sponsor_profile"
    VIEW_SPONSOR_PROFILE = "view_sponsor_profile"
    APPROVE_SPONSOR = "approve_sponsor"
    SUBMIT_SPONSOR_REVIEW = "submit_sponsor_review"

    # Invites
    CREATE_INVITE = "create_invite"
    VIEW_INVITES = "view_invites"

    # Deals
    CREATE_DEAL = "create_deal"
    EDIT_DEAL = "edit_deal"
    SUBMIT_DEAL_OUTCOME = "submit_deal_outcome"

    # Onboarding
    VIEW_ONBOARDING = "view_onboarding"
    DISMISS_PROMPT = "dismiss_prompt"


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
        # Non-admin needs explicit roles or can_review_verifications.
        if _has_role(user, {"admin"}):
            return Decision(True, "ok")
        if action == Actions.REVIEW_VERIFICATION and getattr(user, "can_review_verifications", False):
            return Decision(True, "reviewer")
        return Decision(False, "forbidden")

    # Analytics and reporting (admin only)
    if action in {Actions.VIEW_ANALYTICS, Actions.EXPORT_ANALYTICS, Actions.VIEW_REPORTS, Actions.RESOLVE_REPORT}:
        return Decision(False, "forbidden")

    # Report submission (verified users only)
    if action == Actions.SUBMIT_REPORT:
        if is_verified(user):
            return Decision(True, "ok")
        return Decision(False, "verification_required")

    # Sponsor actions
    if action == Actions.SUBMIT_SPONSOR_PROFILE:
        return Decision(True, "ok")

    if action == Actions.VIEW_SPONSOR_PROFILE:
        return Decision(True, "ok")

    if action == Actions.APPROVE_SPONSOR:
        return Decision(False, "forbidden")

    if action == Actions.SUBMIT_SPONSOR_REVIEW:
        if is_verified(user):
            return Decision(True, "ok")
        return Decision(False, "verification_required")

    # Invites (verified users with credits)
    if action == Actions.CREATE_INVITE:
        if is_verified(user) and getattr(user, "invite_credits", 0) > 0:
            return Decision(True, "ok")
        return Decision(False, "no_invite_credits")

    if action == Actions.VIEW_INVITES:
        return Decision(True, "ok")

    # Deals
    if action == Actions.CREATE_DEAL:
        if is_verified(user):
            return Decision(True, "ok")
        return Decision(False, "verification_required")

    if action == Actions.SUBMIT_DEAL_OUTCOME:
        return Decision(True, "ok")

    # Onboarding
    if action in {Actions.VIEW_ONBOARDING, Actions.DISMISS_PROMPT}:
        return Decision(True, "ok")

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
