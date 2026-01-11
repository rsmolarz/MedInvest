"""
Events Routes - Conferences and networking events
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import Event, EventRegistration

events_bp = Blueprint('events', __name__, url_prefix='/events')


@events_bp.route('/')
def list_events():
    """List upcoming and past events"""
    now = datetime.utcnow()
    
    upcoming = Event.query.filter(
        Event.start_date > now,
        Event.is_published == True
    ).order_by(Event.start_date.asc()).all()
    
    past = Event.query.filter(
        Event.start_date < now,
        Event.is_published == True
    ).order_by(Event.start_date.desc()).limit(10).all()
    
    return render_template('events/list.html',
                         upcoming=upcoming,
                         past=past)


@events_bp.route('/<int:event_id>')
def view_event(event_id):
    """View event details"""
    event = Event.query.get_or_404(event_id)
    
    # Check early bird pricing
    now = datetime.utcnow()
    is_early_bird = event.early_bird_ends and now < event.early_bird_ends
    current_price = event.early_bird_price if is_early_bird and event.early_bird_price else event.regular_price
    
    # Check if user is registered
    registration = None
    if current_user.is_authenticated:
        registration = EventRegistration.query.filter_by(
            event_id=event_id,
            user_id=current_user.id
        ).first()
    
    # Calculate spots left
    spots_left = None
    if event.max_attendees:
        spots_left = event.max_attendees - event.current_attendees
    
    return render_template('events/detail.html',
                         event=event,
                         registration=registration,
                         current_price=current_price,
                         is_early_bird=is_early_bird,
                         spots_left=spots_left)


@events_bp.route('/<int:event_id>/register', methods=['POST'])
@login_required
def register_event(event_id):
    """Register for an event"""
    event = Event.query.get_or_404(event_id)
    
    # Check capacity
    if event.max_attendees and event.current_attendees >= event.max_attendees:
        return jsonify({'error': 'Event is sold out'}), 400
    
    # Check if already registered
    existing = EventRegistration.query.filter_by(
        event_id=event_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already registered'}), 400
    
    # Determine price
    now = datetime.utcnow()
    is_early_bird = event.early_bird_ends and now < event.early_bird_ends
    price = event.early_bird_price if is_early_bird and event.early_bird_price else event.regular_price
    
    registration = EventRegistration(
        event_id=event_id,
        user_id=current_user.id,
        ticket_type='early_bird' if is_early_bird else 'regular',
        purchase_price=price
    )
    
    event.current_attendees += 1
    current_user.add_points(25)
    
    db.session.add(registration)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Registration successful! Check your email for details.'
    })
