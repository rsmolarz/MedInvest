from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from flask import jsonify, request, redirect, url_for, flash
from flask_login import current_user


def _is_verified() -> bool:
    """Treat either legacy is_verified or new verification_status as verified."""
    return bool(getattr(current_user, "is_verified", False)) or getattr(current_user, "verification_status", "unverified") == "verified"


def _wants_json() -> bool:
    """Check if request expects JSON response."""
    return (
        request.is_json or 
        request.path.startswith('/api/') or
        request.headers.get('Accept', '').startswith('application/json')
    )


def require_verified(func: Callable[..., Any]) -> Callable[..., Any]:
    """Require the current user to be a verified physician."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not getattr(current_user, "is_authenticated", False):
            if _wants_json():
                return jsonify({"error": "authentication_required"}), 401
            return redirect(url_for('login'))
        if not _is_verified():
            if _wants_json():
                return jsonify({"error": "verification_required"}), 403
            flash('This feature requires account verification. Please complete your verification to access it.', 'warning')
            return redirect(url_for('submit_verification'))
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
