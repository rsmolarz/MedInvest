"""
AMA Routes - Expert Ask Me Anything sessions
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
from app import db
from models import ExpertAMA, AMAQuestion, AMARegistration, AMAStatus
from facebook_page import share_ama, is_facebook_configured

ama_bp = Blueprint('ama', __name__, url_prefix='/ama')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@ama_bp.route('/')
def list_amas():
    """List all AMAs - upcoming, live, and past"""
    now = datetime.utcnow()
    
    # Live AMAs
    live = ExpertAMA.query.filter(
        ExpertAMA.status == 'live'
    ).all()
    
    # Upcoming AMAs
    upcoming = ExpertAMA.query.filter(
        ExpertAMA.scheduled_for > now,
        ExpertAMA.status == 'scheduled'
    ).order_by(ExpertAMA.scheduled_for.asc()).limit(10).all()
    
    # Past AMAs with recordings
    past = ExpertAMA.query.filter(
        ExpertAMA.status == 'ended'
    ).order_by(ExpertAMA.scheduled_for.desc()).limit(20).all()
    
    # User's registrations
    user_registrations = []
    if current_user.is_authenticated:
        regs = AMARegistration.query.filter_by(user_id=current_user.id).all()
        user_registrations = [r.ama_id for r in regs]
    
    return render_template('ama/list.html',
                         live=live,
                         upcoming=upcoming,
                         past=past,
                         user_registrations=user_registrations)


@ama_bp.route('/<int:ama_id>')
def view_ama(ama_id):
    """View AMA details"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    # Check premium access
    if ama.is_premium_only and current_user.is_authenticated and not current_user.is_premium:
        flash('This AMA is for premium members only', 'warning')
    
    # Get questions sorted by upvotes
    questions = AMAQuestion.query.filter_by(ama_id=ama_id)\
                                .order_by(AMAQuestion.upvotes.desc()).all()
    
    # Check if user is registered
    is_registered = False
    if current_user.is_authenticated:
        reg = AMARegistration.query.filter_by(
            ama_id=ama_id, 
            user_id=current_user.id
        ).first()
        is_registered = reg is not None
    
    return render_template('ama/detail.html',
                         ama=ama,
                         questions=questions,
                         is_registered=is_registered)


@ama_bp.route('/<int:ama_id>/register', methods=['POST'])
@login_required
def register_ama(ama_id):
    """Register for an AMA"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    # Check premium access
    if ama.is_premium_only and not current_user.is_premium:
        return jsonify({'error': 'Premium membership required'}), 403
    
    # Check if already registered
    existing = AMARegistration.query.filter_by(
        ama_id=ama_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already registered'}), 400
    
    registration = AMARegistration(
        ama_id=ama_id,
        user_id=current_user.id
    )
    
    ama.participant_count += 1
    current_user.add_points(10)
    
    db.session.add(registration)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Registered successfully!'})


@ama_bp.route('/<int:ama_id>/question', methods=['POST'])
@login_required
def ask_question(ama_id):
    """Submit a question for an AMA"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    data = request.get_json()
    question_text = data.get('question', '').strip()
    is_anonymous = data.get('is_anonymous', False)
    
    if not question_text:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    question = AMAQuestion(
        ama_id=ama_id,
        user_id=current_user.id,
        question=question_text,
        is_anonymous=is_anonymous
    )
    
    ama.question_count += 1
    current_user.add_points(5)
    
    db.session.add(question)
    db.session.commit()
    
    return jsonify({'success': True, 'question_id': question.id})


@ama_bp.route('/question/<int:question_id>/upvote', methods=['POST'])
@login_required
def upvote_question(question_id):
    """Upvote an AMA question"""
    question = AMAQuestion.query.get_or_404(question_id)
    question.upvotes += 1
    db.session.commit()
    
    return jsonify({'success': True, 'upvotes': question.upvotes})


@ama_bp.route('/<int:ama_id>/live')
@login_required
def live_ama(ama_id):
    """Live AMA interface"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    # Check premium access
    if ama.is_premium_only and not current_user.is_premium:
        flash('This AMA is for premium members only', 'warning')
        return redirect(url_for('subscription.pricing'))
    
    # Check if registered
    registration = AMARegistration.query.filter_by(
        ama_id=ama_id,
        user_id=current_user.id
    ).first()
    
    if not registration:
        flash('Please register for this AMA first', 'warning')
        return redirect(url_for('ama.view_ama', ama_id=ama_id))
    
    # Mark as attended
    registration.attended = True
    db.session.commit()
    
    questions = AMAQuestion.query.filter_by(ama_id=ama_id)\
                                .order_by(AMAQuestion.upvotes.desc()).all()
    
    return render_template('ama/live.html', ama=ama, questions=questions)


@ama_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_ama():
    """Create a new Expert AMA session"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        expert_name = request.form.get('expert_name', '').strip()
        expert_title = request.form.get('expert_title', '').strip()
        expert_bio = request.form.get('expert_bio', '').strip()
        description = request.form.get('description', '').strip()
        scheduled_str = request.form.get('scheduled_for', '')
        duration = request.form.get('duration_minutes', '60')
        is_premium = request.form.get('is_premium_only') == 'on'
        expert_image_url = request.form.get('expert_image_url', '').strip()
        
        if not title:
            flash('AMA title is required', 'error')
            return redirect(url_for('ama.list_amas'))
        
        if not expert_name:
            flash('Expert name is required', 'error')
            return redirect(url_for('ama.list_amas'))
        
        if not scheduled_str:
            flash('Scheduled date/time is required', 'error')
            return redirect(url_for('ama.list_amas'))
        
        try:
            scheduled_for = datetime.fromisoformat(scheduled_str)
        except ValueError:
            flash('Invalid date/time format', 'error')
            return redirect(url_for('ama.list_amas'))
        
        ama = ExpertAMA(
            title=title,
            expert_name=expert_name,
            expert_title=expert_title,
            expert_bio=expert_bio,
            description=description,
            scheduled_for=scheduled_for,
            duration_minutes=int(duration),
            is_premium_only=is_premium,
            expert_image_url=expert_image_url if expert_image_url else None,
            status=AMAStatus.SCHEDULED
        )
        
        db.session.add(ama)
        db.session.commit()
        
        # Auto-post to Facebook
        if is_facebook_configured():
            fb_result = share_ama(ama)
            if fb_result.get('success'):
                flash(f'AMA "{title}" scheduled and shared to Facebook!', 'success')
            else:
                flash(f'AMA "{title}" scheduled! (Facebook post failed: {fb_result.get("error", "unknown")})', 'warning')
        else:
            flash(f'AMA "{title}" scheduled successfully!', 'success')
        
        return redirect(url_for('ama.view_ama', ama_id=ama.id))
    
    # For GET requests, redirect to list (modal-based creation)
    return redirect(url_for('ama.list_amas'))


@ama_bp.route('/<int:ama_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_ama(ama_id):
    """Edit an existing AMA"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    ama.title = request.form.get('title', ama.title)
    ama.expert_name = request.form.get('expert_name', ama.expert_name)
    ama.expert_title = request.form.get('expert_title', ama.expert_title)
    ama.expert_bio = request.form.get('expert_bio', ama.expert_bio)
    ama.description = request.form.get('description', ama.description)
    
    scheduled_str = request.form.get('scheduled_for')
    if scheduled_str:
        try:
            ama.scheduled_for = datetime.fromisoformat(scheduled_str)
        except ValueError:
            pass
    
    duration = request.form.get('duration_minutes')
    if duration:
        ama.duration_minutes = int(duration)
    
    ama.is_premium_only = request.form.get('is_premium_only') == 'on'
    
    expert_image_url = request.form.get('expert_image_url', '').strip()
    if expert_image_url:
        ama.expert_image_url = expert_image_url
    
    db.session.commit()
    flash('AMA updated successfully!', 'success')
    return redirect(url_for('ama.view_ama', ama_id=ama_id))


@ama_bp.route('/<int:ama_id>/status', methods=['POST'])
@login_required
@admin_required
def update_status(ama_id):
    """Update AMA status (start live, end)"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    new_status = request.form.get('status')
    
    # Validate against allowed status values
    allowed_statuses = [s.value for s in AMAStatus]
    if new_status not in allowed_statuses:
        flash('Invalid status value', 'error')
        return redirect(url_for('ama.view_ama', ama_id=ama_id))
    
    try:
        ama.status = AMAStatus(new_status)
        db.session.commit()
        flash(f'AMA status updated to {new_status}', 'success')
    except ValueError:
        flash('Invalid status', 'error')
    
    return redirect(url_for('ama.view_ama', ama_id=ama_id))


@ama_bp.route('/<int:ama_id>/share-facebook', methods=['POST'])
@login_required
@admin_required
def share_to_facebook(ama_id):
    """Manually share an AMA to Facebook (admin only)"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    if not is_facebook_configured():
        flash('Facebook integration not configured', 'error')
        return redirect(url_for('ama.view_ama', ama_id=ama_id))
    
    fb_result = share_ama(ama)
    if fb_result.get('success'):
        flash('AMA shared to Facebook successfully!', 'success')
    else:
        flash(f'Facebook post failed: {fb_result.get("error", "unknown")}', 'error')
    
    return redirect(url_for('ama.view_ama', ama_id=ama_id))
