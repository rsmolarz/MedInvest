from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from flask import jsonify
from flask_login import current_user


def _is_verified() -> bool:
    """Treat either legacy is_verified or new verification_status as verified."""
    return bool(getattr(current_user, "is_verified", False)) or getattr(current_user, "verification_status", "unverified") == "verified"


def require_verified(func: Callable[..., Any]) -> Callable[..., Any]:
    """Require the current user to be a verified physician."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not getattr(current_user, "is_authenticated", False):
            return jsonify({"error": "authentication_required"}), 401
        if not _is_verified():
            return jsonify({"error": "verification_required"}), 403
        return func(*args, **kwargs)
    return wrapper


def require_roles(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require one of the given roles. Admin always allowed."""
    role_set = set(roles)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if not getattr(current_user, "is_authenticated", False):
                return jsonify({"error": "authentication_required"}), 401
            current_role = getattr(current_user, "role", "physician")
            if current_role == "admin" or current_role in role_set:
                return func(*args, **kwargs)
            return jsonify({"error": "forbidden", "required_roles": sorted(role_set)}), 403
        return wrapper
    return decorator
