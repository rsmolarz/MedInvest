"""Route-level helpers for authn/authz.

These decorators are thin wrappers over the centralized policy in
`authorization.py`. Keep *all* permission logic in one place.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify
from flask_login import current_user

from authorization import Actions, can, deny_response


def require_verified(func: Callable[..., Any]) -> Callable[..., Any]:
    """Require the current user to be verified (physician-gated area)."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        decision = can(current_user, Actions.ACCESS_PHYSICIAN_AREA)
        if not decision.allowed:
            body, code = deny_response(decision.reason)
            return jsonify(body), code
        return func(*args, **kwargs)

    return wrapper


def require_roles(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require one of the given roles. Admin always allowed."""

    role_set = set(roles)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            decision = can(current_user, Actions.VIEW, required_roles=role_set)
            if not decision.allowed:
                body, code = deny_response(decision.reason)
                # keep backward-compat field for UI
                if decision.reason in {"forbidden_role", "forbidden"}:
                    body = {**body, "required_roles": sorted(role_set)}
                return jsonify(body), code
            return func(*args, **kwargs)

        return wrapper

    return decorator
