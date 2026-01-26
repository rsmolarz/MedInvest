"""Content Moderation Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from utils.content_moderation import ContentModerator, ReportReason
from utils.roles_permissions import permission_required

moderation_bp = Blueprint('moderation', __name__, url_prefix='/moderation')


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


@moderation_bp.route('/')
@login_required
@admin_required
def reports_list():
    """Display pending content reports."""
    reports = ContentModerator.get_pending_reports(limit=100)
    stats = ContentModerator.get_report_stats()
    
    return render_template('moderation/reports.html',
                         reports=reports,
                         stats=stats,
                         reasons=ReportReason)


@moderation_bp.route('/report/<int:report_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    """Resolve a content report."""
    action = request.form.get('action', 'no_action')
    notes = request.form.get('notes', '')
    
    success = ContentModerator.resolve_report(
        report_id=report_id,
        action=action,
        moderator_id=current_user.id,
        notes=notes
    )
    
    if success:
        flash('Report resolved successfully.', 'success')
    else:
        flash('Failed to resolve report.', 'error')
    
    return redirect(url_for('moderation.reports_list'))


@moderation_bp.route('/report/<int:report_id>/dismiss', methods=['POST'])
@login_required
@admin_required
def dismiss_report(report_id):
    """Dismiss a content report."""
    notes = request.form.get('notes', '')
    
    success = ContentModerator.dismiss_report(
        report_id=report_id,
        moderator_id=current_user.id,
        notes=notes
    )
    
    if success:
        flash('Report dismissed.', 'success')
    else:
        flash('Failed to dismiss report.', 'error')
    
    return redirect(url_for('moderation.reports_list'))


@moderation_bp.route('/user/<int:user_id>/warn', methods=['POST'])
@login_required
@admin_required
def warn_user(user_id):
    """Issue a warning to a user."""
    reason = request.form.get('reason', '')
    
    success = ContentModerator.warn_user(
        user_id=user_id,
        moderator_id=current_user.id,
        reason=reason
    )
    
    if success:
        flash('Warning issued successfully.', 'success')
    else:
        flash('Failed to issue warning.', 'error')
    
    return redirect(request.referrer or url_for('moderation.reports_list'))


@moderation_bp.route('/user/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    """Ban a user."""
    reason = request.form.get('reason', '')
    duration = request.form.get('duration')
    duration_days = int(duration) if duration else None
    
    success = ContentModerator.ban_user(
        user_id=user_id,
        moderator_id=current_user.id,
        reason=reason,
        duration_days=duration_days
    )
    
    if success:
        flash('User banned successfully.', 'success')
    else:
        flash('Failed to ban user.', 'error')
    
    return redirect(request.referrer or url_for('moderation.reports_list'))


@moderation_bp.route('/stats')
@login_required
@admin_required
def stats_api():
    """Get moderation stats as JSON."""
    stats = ContentModerator.get_report_stats()
    return jsonify(stats)


@moderation_bp.route('/report', methods=['POST'])
@login_required
def submit_report():
    """Submit a content report (user-facing)."""
    entity_type = request.form.get('entity_type')
    entity_id = request.form.get('entity_id', type=int)
    reason = request.form.get('reason')
    details = request.form.get('details', '')
    
    if not all([entity_type, entity_id, reason]):
        flash('Missing required fields.', 'error')
        return redirect(request.referrer or url_for('main.index'))
    
    report_id = ContentModerator.create_report(
        reporter_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        details=details
    )
    
    if report_id:
        flash('Report submitted. Thank you for helping keep our community safe.', 'success')
    else:
        flash('You have already reported this content.', 'info')
    
    return redirect(request.referrer or url_for('main.index'))
