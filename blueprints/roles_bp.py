"""Roles and Permissions Management Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, CustomRole
from utils.roles_permissions import RoleManager, PERMISSIONS, get_user_permissions
import json

roles_bp = Blueprint('roles', __name__, url_prefix='/admin/roles')


def admin_required(f):
    """Decorator to require admin access."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@roles_bp.route('/')
@login_required
@admin_required
def list_roles():
    """List all custom roles."""
    roles = CustomRole.query.order_by(CustomRole.priority.desc()).all()
    return render_template('admin/roles.html', 
                         roles=roles,
                         permissions=PERMISSIONS)


@roles_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_role():
    """Create a new custom role."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#6c757d')
        priority = request.form.get('priority', 1, type=int)
        permissions = request.form.getlist('permissions')
        
        if not name:
            flash('Role name is required.', 'error')
            return redirect(url_for('roles.create_role'))
        
        existing = CustomRole.query.filter_by(name=name).first()
        if existing:
            flash('A role with this name already exists.', 'error')
            return redirect(url_for('roles.create_role'))
        
        role = CustomRole(
            name=name,
            description=description,
            color=color,
            priority=priority,
            permissions=','.join(permissions)
        )
        db.session.add(role)
        db.session.commit()
        
        flash('Role created successfully.', 'success')
        return redirect(url_for('roles.list_roles'))
    
    return render_template('admin/role_form.html',
                         role=None,
                         permissions=PERMISSIONS)


@roles_bp.route('/<int:role_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_role(role_id):
    """Edit a custom role."""
    role = CustomRole.query.get_or_404(role_id)
    
    if request.method == 'POST':
        role.name = request.form.get('name', '').strip()
        role.description = request.form.get('description', '').strip()
        role.color = request.form.get('color', '#6c757d')
        role.priority = request.form.get('priority', 1, type=int)
        role.permissions = ','.join(request.form.getlist('permissions'))
        
        db.session.commit()
        flash('Role updated successfully.', 'success')
        return redirect(url_for('roles.list_roles'))
    
    current_permissions = role.permissions.split(',') if role.permissions else []
    
    return render_template('admin/role_form.html',
                         role=role,
                         current_permissions=current_permissions,
                         permissions=PERMISSIONS)


@roles_bp.route('/<int:role_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_role(role_id):
    """Delete a custom role."""
    role = CustomRole.query.get_or_404(role_id)
    
    db.session.delete(role)
    db.session.commit()
    
    flash('Role deleted.', 'success')
    return redirect(url_for('roles.list_roles'))


@roles_bp.route('/users')
@login_required
@admin_required
def user_roles():
    """View and manage user roles."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    roles = CustomRole.query.order_by(CustomRole.name).all()
    
    return render_template('admin/user_roles.html',
                         users=users,
                         roles=roles,
                         search=search)


@roles_bp.route('/users/<int:user_id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_role(user_id):
    """Assign a role to a user."""
    user = User.query.get_or_404(user_id)
    role_id = request.form.get('role_id', type=int)
    
    if role_id:
        role = CustomRole.query.get(role_id)
        if role:
            user.custom_role_id = role_id
            db.session.commit()
            flash(f'Role "{role.name}" assigned to {user.username}.', 'success')
    else:
        user.custom_role_id = None
        db.session.commit()
        flash(f'Role removed from {user.username}.', 'success')
    
    return redirect(request.referrer or url_for('roles.user_roles'))


@roles_bp.route('/users/<int:user_id>/permissions')
@login_required
@admin_required
def user_permissions_api(user_id):
    """Get user's effective permissions as JSON."""
    user = User.query.get_or_404(user_id)
    permissions = list(get_user_permissions(user))
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'is_admin': user.is_admin,
        'permissions': permissions
    })
