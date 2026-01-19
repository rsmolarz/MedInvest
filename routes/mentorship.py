"""
Mentorship Routes - Peer mentorship program
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import User, Mentorship, MentorshipStatus, MentorApplication

mentorship_bp = Blueprint('mentorship', __name__, url_prefix='/mentorship')


@mentorship_bp.route('/')
@login_required
def index():
    """Mentorship dashboard"""
    # Find approved mentors from MentorApplication
    approved_applications = MentorApplication.query.filter_by(status='approved').all()
    mentor_ids = [app.user_id for app in approved_applications if app.user_id != current_user.id]
    
    mentors = []
    mentor_specialties = {}
    if mentor_ids:
        mentors = User.query.filter(User.id.in_(mentor_ids)).order_by(User.points.desc()).all()
        # Map mentor specialties from their applications
        for app in approved_applications:
            mentor_specialties[app.user_id] = app.specialty_areas
    
    # User's mentorship relationships
    as_mentor = Mentorship.query.filter_by(mentor_id=current_user.id).all()
    as_mentee = Mentorship.query.filter_by(mentee_id=current_user.id).all()
    
    # Check if current user is an approved mentor
    is_mentor = MentorApplication.query.filter_by(
        user_id=current_user.id, 
        status='approved'
    ).first() is not None
    
    return render_template('mentorship/index.html',
                         mentors=mentors,
                         mentor_specialties=mentor_specialties,
                         as_mentor=as_mentor,
                         as_mentee=as_mentee,
                         is_mentor=is_mentor)


@mentorship_bp.route('/request/<int:mentor_id>', methods=['POST'])
@login_required
def request_mentor(mentor_id):
    """Request mentorship from a user"""
    mentor = User.query.get_or_404(mentor_id)
    
    if mentor_id == current_user.id:
        return jsonify({'error': 'Cannot mentor yourself'}), 400
    
    # Check for existing relationship
    existing = Mentorship.query.filter_by(
        mentor_id=mentor_id,
        mentee_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Mentorship already exists'}), 400
    
    data = request.get_json()
    
    mentorship = Mentorship(
        mentor_id=mentor_id,
        mentee_id=current_user.id,
        focus_areas=data.get('focus_areas'),
        status=MentorshipStatus.PENDING
    )
    
    db.session.add(mentorship)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Mentorship request sent!'
    })


@mentorship_bp.route('/<int:mentorship_id>/accept', methods=['POST'])
@login_required
def accept_mentorship(mentorship_id):
    """Accept a mentorship request"""
    mentorship = Mentorship.query.get_or_404(mentorship_id)
    
    if mentorship.mentor_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    
    mentorship.status = MentorshipStatus.ACTIVE
    mentorship.start_date = datetime.utcnow()
    
    # Award points to both parties
    current_user.add_points(50)
    mentorship.mentee.add_points(25)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Mentorship accepted!'
    })


@mentorship_bp.route('/<int:mentorship_id>/decline', methods=['POST'])
@login_required
def decline_mentorship(mentorship_id):
    """Decline a mentorship request"""
    mentorship = Mentorship.query.get_or_404(mentorship_id)
    
    if mentorship.mentor_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    
    db.session.delete(mentorship)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Request declined'})


@mentorship_bp.route('/<int:mentorship_id>/complete', methods=['POST'])
@login_required
def complete_mentorship(mentorship_id):
    """Mark mentorship as completed"""
    mentorship = Mentorship.query.get_or_404(mentorship_id)
    
    if mentorship.mentor_id != current_user.id and mentorship.mentee_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    
    mentorship.status = MentorshipStatus.COMPLETED
    
    # Bonus points for completion
    mentorship.mentor.add_points(100)
    mentorship.mentee.add_points(75)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Mentorship completed!'})


# ============== Mentor Application Routes ==============

@mentorship_bp.route('/become-a-mentor')
@login_required
def become_mentor():
    """Show mentor application form"""
    # Check if user already has an application
    existing_app = MentorApplication.query.filter_by(user_id=current_user.id).first()
    
    return render_template('mentorship/apply.html', existing_application=existing_app)


@mentorship_bp.route('/apply', methods=['POST'])
@login_required
def submit_mentor_application():
    """Submit mentor application"""
    # Check for existing pending/approved application
    existing = MentorApplication.query.filter(
        MentorApplication.user_id == current_user.id,
        MentorApplication.status.in_(['pending', 'approved'])
    ).first()
    
    if existing:
        if existing.status == 'approved':
            flash('You are already an approved mentor!', 'info')
        else:
            flash('You already have a pending application.', 'warning')
        return redirect(url_for('mentorship.become_mentor'))
    
    application = MentorApplication(
        user_id=current_user.id,
        specialty_areas=request.form.get('specialty_areas'),
        years_investing=request.form.get('years_investing', type=int),
        investment_experience=request.form.get('investment_experience'),
        mentoring_experience=request.form.get('mentoring_experience'),
        motivation=request.form.get('motivation'),
        availability=request.form.get('availability'),
        linkedin_url=request.form.get('linkedin_url')
    )
    
    db.session.add(application)
    db.session.commit()
    
    flash('Your mentor application has been submitted! We will review it shortly.', 'success')
    return redirect(url_for('mentorship.index'))


def is_approved_mentor(user):
    """Check if a user is an approved mentor"""
    app = MentorApplication.query.filter_by(user_id=user.id, status='approved').first()
    return app is not None
