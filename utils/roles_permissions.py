"""
Advanced User Roles and Permissions System.
Provides role-based access control (RBAC) for the platform.
"""
from functools import wraps
from typing import List, Set, Optional, Dict
from flask import abort, current_app
from flask_login import current_user
from app import db
import logging

logger = logging.getLogger(__name__)


PERMISSIONS = {
    'post': 'Create posts',
    'comment': 'Create comments',
    'like': 'Like content',
    'share': 'Share content',
    'view_deals': 'View investment deals',
    'create_deals': 'Create investment deals',
    'enroll_courses': 'Enroll in courses',
    'create_courses': 'Create courses',
    'create_events': 'Create events',
    'host_amas': 'Host AMA sessions',
    'moderate': 'Moderate content',
    'view_reports': 'View content reports',
    'resolve_reports': 'Resolve reports',
    'ban_users': 'Ban/suspend users',
    'delete_content': 'Delete any content',
    'manage_users': 'Manage user accounts',
    'manage_roles': 'Manage roles',
    'view_analytics': 'View analytics',
    'manage_settings': 'Manage platform settings',
    'manage_webhooks': 'Manage webhooks',
    'manage_deals': 'Manage all deals',
    'verify_users': 'Verify user accounts',
}

DEFAULT_ROLES = {
    'member': {
        'name': 'Member',
        'description': 'Standard user',
        'permissions': ['post', 'comment', 'like', 'share', 'enroll_courses'],
        'color': '#6c757d',
        'priority': 1,
    },
    'verified': {
        'name': 'Verified',
        'description': 'Verified medical professional',
        'permissions': ['post', 'comment', 'like', 'share', 'view_deals', 'enroll_courses', 'create_events'],
        'color': '#17a2b8',
        'priority': 2,
    },
    'contributor': {
        'name': 'Contributor',
        'description': 'Content contributor',
        'permissions': ['post', 'comment', 'like', 'share', 'view_deals', 'enroll_courses', 
                       'create_courses', 'host_amas'],
        'color': '#28a745',
        'priority': 3,
    },
    'moderator': {
        'name': 'Moderator',
        'description': 'Content moderator',
        'permissions': ['post', 'comment', 'like', 'share', 'view_deals', 'enroll_courses',
                       'moderate', 'view_reports', 'resolve_reports', 'ban_users', 'delete_content'],
        'color': '#ffc107',
        'priority': 4,
    },
    'admin': {
        'name': 'Admin',
        'description': 'Platform administrator',
        'permissions': list(PERMISSIONS.keys()),
        'color': '#dc3545',
        'priority': 10,
    },
}


def get_user_permissions(user) -> Set[str]:
    """Get all permissions for a user based on their role."""
    if user.is_admin:
        return set(PERMISSIONS.keys())
    
    role = getattr(user, 'role', 'member') or 'member'
    
    if role in DEFAULT_ROLES:
        return set(DEFAULT_ROLES[role]['permissions'])
    
    from models import CustomRole
    custom_role = CustomRole.query.filter_by(name=role).first()
    if custom_role:
        return set(custom_role.permissions.split(',')) if custom_role.permissions else set()
    
    return set(DEFAULT_ROLES['member']['permissions'])


def has_permission(user, permission: str) -> bool:
    """Check if a user has a specific permission."""
    if not user or not user.is_authenticated:
        return False
    
    if user.is_admin:
        return True
    
    permissions = get_user_permissions(user)
    return permission in permissions


def has_any_permission(user, permissions: List[str]) -> bool:
    """Check if a user has any of the specified permissions."""
    user_permissions = get_user_permissions(user)
    return bool(user_permissions.intersection(set(permissions)))


def has_all_permissions(user, permissions: List[str]) -> bool:
    """Check if a user has all of the specified permissions."""
    user_permissions = get_user_permissions(user)
    return set(permissions).issubset(user_permissions)


def permission_required(permission: str):
    """Decorator to require a specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            if not has_permission(current_user, permission):
                logger.warning(f"Permission denied: {current_user.username} lacks {permission}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def any_permission_required(*permissions):
    """Decorator to require any of the specified permissions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            if not has_any_permission(current_user, list(permissions)):
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(role: str):
    """Decorator to require a specific role or higher."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            user_role = getattr(current_user, 'role', 'member') or 'member'
            
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            required_priority = DEFAULT_ROLES.get(role, {}).get('priority', 0)
            user_priority = DEFAULT_ROLES.get(user_role, {}).get('priority', 0)
            
            if user_priority < required_priority:
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


class RoleManager:
    """Manager for role operations."""
    
    @staticmethod
    def assign_role(user, role: str) -> bool:
        """Assign a role to a user."""
        if role not in DEFAULT_ROLES:
            from models import CustomRole
            if not CustomRole.query.filter_by(name=role).first():
                return False
        
        user.role = role
        db.session.commit()
        
        logger.info(f"Assigned role {role} to user {user.username}")
        return True
    
    @staticmethod
    def remove_role(user) -> bool:
        """Remove role and set to default member."""
        user.role = 'member'
        db.session.commit()
        return True
    
    @staticmethod
    def create_custom_role(
        name: str,
        description: str,
        permissions: List[str],
        color: str = '#6c757d'
    ) -> Optional[int]:
        """Create a custom role."""
        from models import CustomRole
        
        if name in DEFAULT_ROLES:
            return None
        
        existing = CustomRole.query.filter_by(name=name).first()
        if existing:
            return None
        
        valid_permissions = [p for p in permissions if p in PERMISSIONS]
        
        role = CustomRole(
            name=name,
            description=description,
            permissions=','.join(valid_permissions),
            color=color
        )
        db.session.add(role)
        db.session.commit()
        
        return role.id
    
    @staticmethod
    def update_custom_role(
        role_id: int,
        name: str = None,
        description: str = None,
        permissions: List[str] = None,
        color: str = None
    ) -> bool:
        """Update a custom role."""
        from models import CustomRole
        
        role = CustomRole.query.get(role_id)
        if not role:
            return False
        
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if permissions is not None:
            valid_permissions = [p for p in permissions if p in PERMISSIONS]
            role.permissions = ','.join(valid_permissions)
        if color is not None:
            role.color = color
        
        db.session.commit()
        return True
    
    @staticmethod
    def delete_custom_role(role_id: int) -> bool:
        """Delete a custom role and reset affected users to member."""
        from models import CustomRole, User
        
        role = CustomRole.query.get(role_id)
        if not role:
            return False
        
        User.query.filter_by(role=role.name).update({'role': 'member'})
        
        db.session.delete(role)
        db.session.commit()
        
        return True
    
    @staticmethod
    def get_role_stats() -> Dict:
        """Get statistics about role distribution."""
        from models import User, CustomRole
        
        stats = {
            'admin_count': User.query.filter_by(is_admin=True).count(),
            'moderator_count': User.query.filter_by(role='moderator').count(),
            'verified_count': User.query.filter(
                User.verification_status == 'verified'
            ).count(),
            'member_count': User.query.filter(
                User.role.in_(['member', None])
            ).count(),
            'custom_roles': []
        }
        
        custom_roles = CustomRole.query.all()
        for role in custom_roles:
            stats['custom_roles'].append({
                'id': role.id,
                'name': role.name,
                'user_count': User.query.filter_by(role=role.name).count(),
                'permissions': role.permissions.split(',') if role.permissions else [],
                'color': role.color
            })
        
        return stats
