"""
Content Moderation Dashboard - Admin tools for content review and user management
"""
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from functools import wraps

logger = logging.getLogger(__name__)

moderation_bp = Blueprint('moderation', __name__, url_prefix='/moderation')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.', 'error')
            return redirect(url_for('main.feed'))
        return f(*args, **kwargs)
    return wrapper


@moderation_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Moderation dashboard overview"""
    from models import ContentReport, Post, User, ModerationEvent
    
    pending_reports = ContentReport.query.filter_by(status='pending').count()
    resolved_today = ContentReport.query.filter(
        ContentReport.status.in_(['resolved', 'dismissed']),
        ContentReport.resolved_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    
    flagged_posts = Post.query.filter_by(is_hidden=True).count()
    
    pending_verifications = User.query.filter_by(
        verification_status='pending'
    ).count() if hasattr(User, 'verification_status') else 0
    
    recent_actions = ModerationEvent.query.order_by(
        ModerationEvent.created_at.desc()
    ).limit(10).all()
    
    recent_reports = ContentReport.query.filter_by(
        status='pending'
    ).order_by(ContentReport.created_at.desc()).limit(10).all()
    
    return render_template('moderation/dashboard.html',
                         pending_reports=pending_reports,
                         resolved_today=resolved_today,
                         flagged_posts=flagged_posts,
                         pending_verifications=pending_verifications,
                         recent_actions=recent_actions,
                         recent_reports=recent_reports)


@moderation_bp.route('/reports')
@login_required
@admin_required
def reports_queue():
    """View all content reports"""
    from models import ContentReport
    
    status_filter = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)
    
    query = ContentReport.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    reports = query.order_by(ContentReport.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('moderation/reports.html',
                         reports=reports,
                         status_filter=status_filter)


@moderation_bp.route('/reports/<int:report_id>')
@login_required
@admin_required
def view_report(report_id):
    """View a specific report"""
    from models import ContentReport, Post, Comment, ModerationEvent
    
    report = ContentReport.query.get_or_404(report_id)
    
    content = None
    if report.content_type == 'post':
        content = Post.query.get(report.content_id)
    elif report.content_type == 'comment':
        content = Comment.query.get(report.content_id)
    
    previous_actions = ModerationEvent.query.filter_by(
        target_type=report.content_type,
        target_id=report.content_id
    ).order_by(ModerationEvent.created_at.desc()).all()
    
    return render_template('moderation/report_detail.html',
                         report=report,
                         content=content,
                         previous_actions=previous_actions)


@moderation_bp.route('/reports/<int:report_id>/action', methods=['POST'])
@login_required
@admin_required
def take_action(report_id):
    """Take moderation action on a report"""
    from models import ContentReport, Post, Comment, User, ModerationEvent
    
    report = ContentReport.query.get_or_404(report_id)
    action = request.form.get('action')
    notes = request.form.get('notes', '')
    
    valid_actions = ['approve', 'reject', 'hide', 'quarantine', 'warn_user', 'ban_user', 'dismiss']
    if action not in valid_actions:
        flash('Invalid action.', 'error')
        return redirect(url_for('moderation.view_report', report_id=report_id))
    
    content = None
    content_author_id = None
    
    if report.content_type == 'post':
        content = Post.query.get(report.content_id)
        if content:
            content_author_id = content.author_id
    elif report.content_type == 'comment':
        content = Comment.query.get(report.content_id)
        if content:
            content_author_id = content.user_id
    
    if action == 'approve':
        if content and hasattr(content, 'is_hidden'):
            content.is_hidden = False
        report.status = 'dismissed'
        report.resolution = 'Content approved - no action needed'
        
    elif action == 'reject' or action == 'hide':
        if content and hasattr(content, 'is_hidden'):
            content.is_hidden = True
        report.status = 'resolved'
        report.resolution = 'Content hidden for policy violation'
        
    elif action == 'quarantine':
        if content and hasattr(content, 'is_quarantined'):
            content.is_quarantined = True
        report.status = 'resolved'
        report.resolution = 'Content quarantined for review'
        
    elif action == 'warn_user':
        if content_author_id:
            user = User.query.get(content_author_id)
            if user:
                user.warning_count = (user.warning_count or 0) + 1
        report.status = 'resolved'
        report.resolution = 'User warned'
        
    elif action == 'ban_user':
        if content_author_id:
            user = User.query.get(content_author_id)
            if user:
                user.is_banned = True
                user.banned_at = datetime.utcnow()
                user.ban_reason = notes or 'Policy violation'
        report.status = 'resolved'
        report.resolution = 'User banned'
        
    elif action == 'dismiss':
        report.status = 'dismissed'
        report.resolution = 'Report dismissed - no action needed'
    
    report.resolved_at = datetime.utcnow()
    report.resolved_by_id = current_user.id
    
    mod_event = ModerationEvent(
        moderator_id=current_user.id,
        action=action,
        target_type=report.content_type,
        target_id=report.content_id,
        target_user_id=content_author_id,
        reason=report.reason,
        notes=notes
    )
    db.session.add(mod_event)
    
    db.session.commit()
    
    logger.info(f"Moderation action: {action} on {report.content_type}:{report.content_id} by admin {current_user.id}")
    
    flash(f'Action "{action}" taken successfully.', 'success')
    return redirect(url_for('moderation.reports_queue'))


@moderation_bp.route('/users')
@login_required
@admin_required
def users_list():
    """List users for moderation"""
    from models import User
    
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    search = request.args.get('search', '')
    
    query = User.query
    
    if filter_type == 'banned':
        query = query.filter_by(is_banned=True)
    elif filter_type == 'warned':
        query = query.filter(User.warning_count > 0)
    elif filter_type == 'unverified':
        query = query.filter_by(is_verified=False)
    elif filter_type == 'pending':
        if hasattr(User, 'verification_status'):
            query = query.filter_by(verification_status='pending')
    
    if search:
        query = query.filter(
            db.or_(
                User.email.ilike(f'%{search}%'),
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%')
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('moderation/users.html',
                         users=users,
                         filter_type=filter_type,
                         search=search)


@moderation_bp.route('/users/<int:user_id>/action', methods=['POST'])
@login_required
@admin_required
def user_action(user_id):
    """Take moderation action on a user"""
    from models import User, ModerationEvent
    
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    reason = request.form.get('reason', '')
    
    if action == 'ban':
        user.is_banned = True
        user.banned_at = datetime.utcnow()
        user.ban_reason = reason
        flash(f'User {user.full_name} has been banned.', 'warning')
        
    elif action == 'unban':
        user.is_banned = False
        user.banned_at = None
        user.ban_reason = None
        flash(f'User {user.full_name} has been unbanned.', 'success')
        
    elif action == 'warn':
        user.warning_count = (user.warning_count or 0) + 1
        flash(f'Warning issued to {user.full_name}.', 'info')
        
    elif action == 'verify':
        user.is_verified = True
        if hasattr(user, 'verification_status'):
            user.verification_status = 'approved'
        flash(f'User {user.full_name} has been verified.', 'success')
        
    elif action == 'unverify':
        user.is_verified = False
        flash(f'Verification removed from {user.full_name}.', 'info')
    
    mod_event = ModerationEvent(
        moderator_id=current_user.id,
        action=action,
        target_type='user',
        target_id=user_id,
        target_user_id=user_id,
        reason=reason
    )
    db.session.add(mod_event)
    db.session.commit()
    
    return redirect(url_for('moderation.users_list'))


@moderation_bp.route('/audit-log')
@login_required
@admin_required
def audit_log():
    """View moderation audit log (HIPAA compliance)"""
    from models import ModerationEvent, User
    
    page = request.args.get('page', 1, type=int)
    moderator_id = request.args.get('moderator', type=int)
    action_filter = request.args.get('action', '')
    
    query = ModerationEvent.query
    
    if moderator_id:
        query = query.filter_by(moderator_id=moderator_id)
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    events = query.order_by(ModerationEvent.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    moderators = User.query.filter_by(is_admin=True).all()
    
    return render_template('moderation/audit_log.html',
                         events=events,
                         moderators=moderators,
                         moderator_id=moderator_id,
                         action_filter=action_filter)


@moderation_bp.route('/keywords')
@login_required
@admin_required
def keyword_filters():
    """Manage content filtering keywords"""
    from models import BlockedKeyword
    
    keywords = BlockedKeyword.query.order_by(BlockedKeyword.created_at.desc()).all() if hasattr(db.Model, 'BlockedKeyword') else []
    
    return render_template('moderation/keywords.html', keywords=keywords)


@moderation_bp.route('/keywords/add', methods=['POST'])
@login_required
@admin_required
def add_keyword():
    """Add a blocked keyword"""
    keyword = request.form.get('keyword', '').strip().lower()
    severity = request.form.get('severity', 'low')
    action = request.form.get('action', 'flag')
    
    if not keyword:
        flash('Keyword cannot be empty.', 'error')
        return redirect(url_for('moderation.keyword_filters'))
    
    try:
        from models import BlockedKeyword
        
        existing = BlockedKeyword.query.filter_by(keyword=keyword).first()
        if existing:
            flash('Keyword already exists.', 'warning')
            return redirect(url_for('moderation.keyword_filters'))
        
        new_keyword = BlockedKeyword(
            keyword=keyword,
            severity=severity,
            action=action,
            created_by_id=current_user.id
        )
        db.session.add(new_keyword)
        db.session.commit()
        
        flash(f'Keyword "{keyword}" added to filter list.', 'success')
    except Exception as e:
        logger.error(f"Error adding keyword: {e}")
        flash('Error adding keyword.', 'error')
    
    return redirect(url_for('moderation.keyword_filters'))


@moderation_bp.route('/api/check-content', methods=['POST'])
@login_required
def check_content():
    """API endpoint to check content against filters"""
    content = request.json.get('content', '')
    
    if not content:
        return jsonify({'flagged': False, 'reasons': []})
    
    flagged = False
    reasons = []
    
    try:
        from models import BlockedKeyword
        keywords = BlockedKeyword.query.filter_by(is_active=True).all()
        
        content_lower = content.lower()
        for kw in keywords:
            if kw.keyword in content_lower:
                flagged = True
                reasons.append({
                    'keyword': kw.keyword,
                    'severity': kw.severity,
                    'action': kw.action
                })
    except Exception as e:
        logger.error(f"Error checking content: {e}")
    
    return jsonify({
        'flagged': flagged,
        'reasons': reasons
    })


@moderation_bp.route('/stats')
@login_required
@admin_required
def moderation_stats():
    """Moderation statistics and analytics"""
    from models import ContentReport, ModerationEvent, User
    from sqlalchemy import func
    
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    reports_by_status = db.session.query(
        ContentReport.status,
        func.count(ContentReport.id)
    ).group_by(ContentReport.status).all()
    
    reports_by_reason = db.session.query(
        ContentReport.reason,
        func.count(ContentReport.id)
    ).group_by(ContentReport.reason).order_by(func.count(ContentReport.id).desc()).limit(10).all()
    
    actions_by_type = db.session.query(
        ModerationEvent.action,
        func.count(ModerationEvent.id)
    ).filter(
        ModerationEvent.created_at >= month_ago
    ).group_by(ModerationEvent.action).all()
    
    top_moderators = db.session.query(
        User.id,
        User.first_name,
        User.last_name,
        func.count(ModerationEvent.id).label('action_count')
    ).join(ModerationEvent, User.id == ModerationEvent.moderator_id).filter(
        ModerationEvent.created_at >= month_ago
    ).group_by(User.id).order_by(func.count(ModerationEvent.id).desc()).limit(5).all()
    
    return render_template('moderation/stats.html',
                         reports_by_status=dict(reports_by_status),
                         reports_by_reason=reports_by_reason,
                         actions_by_type=dict(actions_by_type),
                         top_moderators=top_moderators)
