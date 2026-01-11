"""
Mentorship Routes - Peer mentorship program
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import User, Mentorship, MentorshipStatus

mentorship_bp = Blueprint('mentorship', __name__, url_prefix='/mentorship')


@mentorship_bp.route('/')
@login_required
def index():
    """Mentorship dashboard"""
    # Find potential mentors (verified users with high points)
    mentors = User.query.filter(
        User.id != current_user.id,
        User.is_verified == True,
        User.points >= 100
    ).order_by(User.points.desc()).limit(20).all()
    
    # User's mentorship relationships
    as_mentor = Mentorship.query.filter_by(mentor_id=current_user.id).all()
    as_mentee = Mentorship.query.filter_by(mentee_id=current_user.id).all()
    
    return render_template('mentorship/index.html',
                         mentors=mentors,
                         as_mentor=as_mentor,
                         as_mentee=as_mentee)


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
