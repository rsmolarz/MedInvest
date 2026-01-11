"""
AMA Routes - Expert Ask Me Anything sessions
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import ExpertAMA, AMAQuestion, AMARegistration, AMAStatus

ama_bp = Blueprint('ama', __name__, url_prefix='/ama')


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
