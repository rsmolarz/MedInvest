"""
Events Routes - Conferences and networking events
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
from app import db
from models import Event, EventRegistration


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

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


@events_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """Create a new event - admin auto-approved, others need approval"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_type = request.form.get('event_type', 'conference')
        location = request.form.get('location', '').strip()
        venue_name = request.form.get('venue_name', '').strip()
        start_date_str = request.form.get('start_date', '')
        end_date_str = request.form.get('end_date', '')
        regular_price = request.form.get('regular_price', '0')
        max_attendees = request.form.get('max_attendees', '')
        is_virtual = request.form.get('is_virtual') == 'on'
        cover_image_url = request.form.get('cover_image_url', '').strip()
        
        if not title:
            flash('Event title is required', 'error')
            return redirect(url_for('events.list_events'))
        
        if not start_date_str:
            flash('Start date is required', 'error')
            return redirect(url_for('events.list_events'))
        
        try:
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str) if end_date_str else start_date
        except ValueError:
            flash('Invalid date format', 'error')
            return redirect(url_for('events.list_events'))
        
        is_admin = getattr(current_user, 'is_admin', False)
        
        event = Event(
            title=title,
            description=description,
            event_type=event_type,
            location=location,
            venue_name=venue_name,
            start_date=start_date,
            end_date=end_date,
            regular_price=float(regular_price) if regular_price else 0,
            max_attendees=int(max_attendees) if max_attendees else None,
            is_virtual=is_virtual,
            cover_image_url=cover_image_url if cover_image_url else None,
            created_by_id=current_user.id,
            is_published=is_admin,
            approval_status='approved' if is_admin else 'pending'
        )
        
        db.session.add(event)
        db.session.commit()
        
        if is_admin:
            flash(f'Event "{title}" created and published!', 'success')
        else:
            flash(f'Event "{title}" submitted for admin approval!', 'success')
        return redirect(url_for('events.view_event', event_id=event.id))
    
    return redirect(url_for('events.list_events'))
