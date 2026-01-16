"""
Admin Routes - Platform administration
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
from app import db
from models import (User, Post, Room, ExpertAMA, AMAStatus, InvestmentDeal, 
                   DealStatus, Course, Event, SubscriptionTier, AdAdvertiser, 
                   AdCampaign, AdCreative, AdImpression, AdClick)
import json
import hmac
import hashlib
import base64
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    return redirect(url_for('admin.analytics'))


@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Platform analytics"""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    stats = {
        'total_users': User.query.count(),
        'premium_users': User.query.filter(User.subscription_tier == 'premium').count(),
        'new_users_week': User.query.filter(User.created_at >= week_ago).count(),
        'new_users_month': User.query.filter(User.created_at >= month_ago).count(),
        'total_posts': Post.query.count(),
        'posts_week': Post.query.filter(Post.created_at >= week_ago).count(),
        'active_deals': InvestmentDeal.query.filter(InvestmentDeal.status == 'active').count(),
        'pending_deals': InvestmentDeal.query.filter(InvestmentDeal.status == 'review').count(),
        'upcoming_amas': ExpertAMA.query.filter(ExpertAMA.status == 'scheduled').count(),
        'total_courses': Course.query.filter_by(is_published=True).count(),
        'total_events': Event.query.filter_by(is_published=True).count(),
        'pending_verifications': User.query.filter(User.verification_status == 'pending').count(),
    }
    
    # Calculate rates
    if stats['total_users'] > 0:
        stats['premium_rate'] = (stats['premium_users'] / stats['total_users']) * 100
    else:
        stats['premium_rate'] = 0
    
    # Estimate monthly revenue (simplified)
    stats['monthly_revenue'] = stats['premium_users'] * 29  # $29/month
    
    return render_template('admin/analytics.html', stats=stats)


@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """User management"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.email.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('admin/users.html', users=users, search=search)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """Toggle admin status"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot modify your own admin status'}), 400
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_admin': user.is_admin
    })


@admin_bp.route('/users/<int:user_id>/toggle-verified', methods=['POST'])
@login_required
@admin_required
def toggle_verified(user_id):
    """Toggle verified status"""
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_verified': user.is_verified
    })


@admin_bp.route('/deals')
@login_required
@admin_required
def manage_deals():
    """Deal management"""
    pending = InvestmentDeal.query.filter_by(status=DealStatus.REVIEW)\
                                  .order_by(InvestmentDeal.created_at.desc()).all()
    active = InvestmentDeal.query.filter_by(status=DealStatus.ACTIVE)\
                                 .order_by(InvestmentDeal.created_at.desc()).all()
    
    return render_template('admin/deals.html', pending=pending, active=active)


@admin_bp.route('/deals/<int:deal_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_deal(deal_id):
    """Approve a deal"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    deal.status = DealStatus.ACTIVE
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Deal approved'})


@admin_bp.route('/deals/<int:deal_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_deal(deal_id):
    """Reject a deal"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    deal.status = DealStatus.REJECTED
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Deal rejected'})


@admin_bp.route('/deals/<int:deal_id>/feature', methods=['POST'])
@login_required
@admin_required
def feature_deal(deal_id):
    """Toggle deal featured status"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    deal.is_featured = not deal.is_featured
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_featured': deal.is_featured
    })


@admin_bp.route('/amas', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_amas():
    """AMA management"""
    if request.method == 'POST':
        # Create new AMA
        scheduled_str = request.form.get('scheduled_for')
        
        ama = ExpertAMA(
            title=request.form.get('title'),
            expert_name=request.form.get('expert_name'),
            expert_title=request.form.get('expert_title'),
            expert_bio=request.form.get('expert_bio'),
            description=request.form.get('description'),
            scheduled_for=datetime.fromisoformat(scheduled_str),
            duration_minutes=int(request.form.get('duration_minutes', 60)),
            is_premium_only=request.form.get('is_premium_only') == 'on',
            status=AMAStatus.SCHEDULED
        )
        
        db.session.add(ama)
        db.session.commit()
        
        flash('AMA created successfully!', 'success')
    
    amas = ExpertAMA.query.order_by(ExpertAMA.scheduled_for.desc()).all()
    return render_template('admin/amas.html', amas=amas)


@admin_bp.route('/amas/<int:ama_id>/status', methods=['POST'])
@login_required
@admin_required
def update_ama_status(ama_id):
    """Update AMA status"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    data = request.get_json()
    new_status = data.get('status')
    
    try:
        ama.status = AMAStatus(new_status)
        db.session.commit()
        return jsonify({'success': True})
    except ValueError:
        return jsonify({'error': 'Invalid status'}), 400


@admin_bp.route('/rooms', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_rooms():
    """Room management"""
    if request.method == 'POST':
        room = Room(
            name=request.form.get('name'),
            slug=request.form.get('slug').lower().replace(' ', '-'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            icon=request.form.get('icon', 'comments'),
            is_premium_only=request.form.get('is_premium_only') == 'on'
        )
        
        db.session.add(room)
        db.session.commit()
        
        flash('Room created!', 'success')
    
    rooms = Room.query.order_by(Room.category, Room.name).all()
    return render_template('admin/rooms.html', rooms=rooms)


# ============================================================================
# ADS ADMIN CRUD ENDPOINTS
# ============================================================================

@admin_bp.route('/ads/advertisers', methods=['GET', 'POST'])
@login_required
@admin_required
def ads_admin_advertisers():
    """Admin: List or create advertisers."""
    if request.method == 'POST':
        data = request.get_json() or {}
        advertiser = AdAdvertiser(
            name=data.get('name', ''),
            category=data.get('category', 'other'),
            compliance_status=data.get('compliance_status', 'active')
        )
        db.session.add(advertiser)
        db.session.commit()
        return jsonify({
            "id": advertiser.id,
            "name": advertiser.name,
            "category": advertiser.category,
            "compliance_status": advertiser.compliance_status
        }), 201
    
    advertisers = AdAdvertiser.query.order_by(AdAdvertiser.id.desc()).limit(200).all()
    return jsonify([{
        "id": a.id,
        "name": a.name,
        "category": a.category,
        "compliance_status": a.compliance_status,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in advertisers])


@admin_bp.route('/ads/campaigns', methods=['GET', 'POST'])
@login_required
@admin_required
def ads_admin_campaigns():
    """Admin: List or create campaigns."""
    if request.method == 'POST':
        data = request.get_json() or {}
        campaign = AdCampaign(
            advertiser_id=data.get('advertiser_id'),
            name=data.get('name', ''),
            start_at=datetime.fromisoformat(data.get('start_at')) if data.get('start_at') else datetime.utcnow(),
            end_at=datetime.fromisoformat(data.get('end_at')) if data.get('end_at') else datetime.utcnow() + timedelta(days=30),
            daily_budget=data.get('daily_budget', 0),
            targeting_json=json.dumps(data.get('targeting_json', {}))
        )
        db.session.add(campaign)
        db.session.commit()
        return jsonify({
            "id": campaign.id,
            "advertiser_id": campaign.advertiser_id,
            "name": campaign.name,
            "start_at": campaign.start_at.isoformat() if campaign.start_at else None,
            "end_at": campaign.end_at.isoformat() if campaign.end_at else None
        }), 201
    
    campaigns = AdCampaign.query.order_by(AdCampaign.id.desc()).limit(200).all()
    return jsonify([{
        "id": c.id,
        "advertiser_id": c.advertiser_id,
        "name": c.name,
        "start_at": c.start_at.isoformat() if c.start_at else None,
        "end_at": c.end_at.isoformat() if c.end_at else None,
        "daily_budget": c.daily_budget,
        "targeting_json": c.targeting_json
    } for c in campaigns])


@admin_bp.route('/ads/creatives', methods=['GET', 'POST'])
@login_required
@admin_required
def ads_admin_creatives():
    """Admin: List or create creatives."""
    if request.method == 'POST':
        data = request.get_json() or {}
        creative = AdCreative(
            campaign_id=data.get('campaign_id'),
            format=data.get('format', 'feed'),
            headline=data.get('headline', ''),
            body=data.get('body', ''),
            image_url=data.get('image_url'),
            cta_text=data.get('cta_text', 'Learn more'),
            landing_url=data.get('landing_url', ''),
            disclaimer_text=data.get('disclaimer_text', ''),
            is_active=True
        )
        db.session.add(creative)
        db.session.commit()
        return jsonify({
            "id": creative.id,
            "campaign_id": creative.campaign_id,
            "format": creative.format,
            "headline": creative.headline,
            "is_active": creative.is_active
        }), 201
    
    creatives = AdCreative.query.order_by(AdCreative.id.desc()).limit(200).all()
    return jsonify([{
        "id": c.id,
        "campaign_id": c.campaign_id,
        "format": c.format,
        "headline": c.headline,
        "body": c.body,
        "image_url": c.image_url,
        "cta_text": c.cta_text,
        "landing_url": c.landing_url,
        "disclaimer_text": c.disclaimer_text,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None
    } for c in creatives])


@admin_bp.route('/ads/dashboard')
@login_required
def ads_dashboard():
    """Visual admin dashboard for managing ads"""
    from flask_login import current_user
    if current_user.email != 'rsmolarz@rsmolarz.com':
        flash('Access denied', 'error')
        return redirect(url_for('main.feed'))
    
    advertisers = AdAdvertiser.query.order_by(AdAdvertiser.id.desc()).all()
    campaigns = AdCampaign.query.order_by(AdCampaign.id.desc()).all()
    creatives = AdCreative.query.order_by(AdCreative.id.desc()).all()
    
    total_impressions = AdImpression.query.count()
    total_clicks = AdClick.query.count()
    
    return render_template('admin/ads_dashboard.html',
                          advertisers=advertisers,
                          campaigns=campaigns,
                          creatives=creatives,
                          total_impressions=total_impressions,
                          total_clicks=total_clicks)


# ============================================================================
# COURSES MANAGEMENT
# ============================================================================

@admin_bp.route('/courses', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_courses():
    """Course management"""
    if request.method == 'POST':
        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description'),
            instructor_name=request.form.get('instructor_name'),
            price=float(request.form.get('price', 0)),
            original_price=float(request.form.get('original_price', 0)) if request.form.get('original_price') else None,
            difficulty_level=request.form.get('difficulty_level'),
            thumbnail_url=request.form.get('thumbnail_url'),
            is_published=request.form.get('is_published') == 'on',
            is_featured=request.form.get('is_featured') == 'on'
        )
        
        db.session.add(course)
        db.session.commit()
        
        flash('Course created successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))
    
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin/courses.html', courses=courses)


@admin_bp.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(course_id):
    """Edit a course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.instructor_name = request.form.get('instructor_name')
        course.price = float(request.form.get('price', 0))
        course.original_price = float(request.form.get('original_price', 0)) if request.form.get('original_price') else None
        course.difficulty_level = request.form.get('difficulty_level')
        course.thumbnail_url = request.form.get('thumbnail_url')
        course.is_published = request.form.get('is_published') == 'on'
        course.is_featured = request.form.get('is_featured') == 'on'
        
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))
    
    return render_template('admin/course_edit.html', course=course)


@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    """Delete a course"""
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Course deleted'})


@admin_bp.route('/courses/<int:course_id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_course_publish(course_id):
    """Toggle course publish status"""
    course = Course.query.get_or_404(course_id)
    course.is_published = not course.is_published
    db.session.commit()
    
    return jsonify({'success': True, 'is_published': course.is_published})


# ============================================================================
# EVENTS MANAGEMENT
# ============================================================================

@admin_bp.route('/events', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_events():
    """Event management"""
    if request.method == 'POST':
        event = Event(
            title=request.form.get('title'),
            description=request.form.get('description'),
            event_type=request.form.get('event_type'),
            start_date=datetime.fromisoformat(request.form.get('start_date')),
            end_date=datetime.fromisoformat(request.form.get('end_date')),
            timezone=request.form.get('timezone', 'America/New_York'),
            is_virtual=request.form.get('is_virtual') == 'on',
            venue_name=request.form.get('venue_name'),
            venue_address=request.form.get('venue_address'),
            meeting_url=request.form.get('meeting_url'),
            regular_price=float(request.form.get('regular_price', 0)),
            early_bird_price=float(request.form.get('early_bird_price', 0)) if request.form.get('early_bird_price') else None,
            vip_price=float(request.form.get('vip_price', 0)) if request.form.get('vip_price') else None,
            max_attendees=int(request.form.get('max_attendees')) if request.form.get('max_attendees') else None,
            banner_url=request.form.get('banner_url'),
            is_published=request.form.get('is_published') == 'on',
            is_featured=request.form.get('is_featured') == 'on'
        )
        
        db.session.add(event)
        db.session.commit()
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin.manage_events'))
    
    events = Event.query.order_by(Event.start_date.desc()).all()
    return render_template('admin/events.html', events=events)


@admin_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_event(event_id):
    """Edit an event"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.event_type = request.form.get('event_type')
        event.start_date = datetime.fromisoformat(request.form.get('start_date'))
        event.end_date = datetime.fromisoformat(request.form.get('end_date'))
        event.timezone = request.form.get('timezone', 'America/New_York')
        event.is_virtual = request.form.get('is_virtual') == 'on'
        event.venue_name = request.form.get('venue_name')
        event.venue_address = request.form.get('venue_address')
        event.meeting_url = request.form.get('meeting_url')
        event.regular_price = float(request.form.get('regular_price', 0))
        event.early_bird_price = float(request.form.get('early_bird_price', 0)) if request.form.get('early_bird_price') else None
        event.vip_price = float(request.form.get('vip_price', 0)) if request.form.get('vip_price') else None
        event.max_attendees = int(request.form.get('max_attendees')) if request.form.get('max_attendees') else None
        event.banner_url = request.form.get('banner_url')
        event.is_published = request.form.get('is_published') == 'on'
        event.is_featured = request.form.get('is_featured') == 'on'
        
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin.manage_events'))
    
    return render_template('admin/event_edit.html', event=event)


@admin_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event(event_id):
    """Delete an event"""
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Event deleted'})


@admin_bp.route('/events/<int:event_id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_event_publish(event_id):
    """Toggle event publish status"""
    event = Event.query.get_or_404(event_id)
    event.is_published = not event.is_published
    db.session.commit()
    
    return jsonify({'success': True, 'is_published': event.is_published})


# =============================================================================
# VERIFICATION MANAGEMENT
# =============================================================================

@admin_bp.route('/verifications')
@login_required
@admin_required
def verification_list():
    """List pending verifications"""
    pending_users = User.query.filter(
        User.verification_status == 'pending'
    ).order_by(User.verification_submitted_at.asc()).all()
    
    return render_template('admin/verification_list.html', pending_users=pending_users)


@admin_bp.route('/verification/<int:user_id>')
@login_required
@admin_required
def verification_review(user_id):
    """Review a user's verification"""
    user = User.query.get_or_404(user_id)
    return render_template('admin/verification_review.html', user=user)


@admin_bp.route('/verification/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_verification(user_id):
    """Approve a user's verification"""
    user = User.query.get_or_404(user_id)
    
    user.verification_status = 'verified'
    user.is_verified = True
    user.verified_at = datetime.utcnow()
    user.license_verified = True
    db.session.commit()
    
    next_pending = User.query.filter(
        User.verification_status == 'pending',
        User.id != user_id
    ).order_by(User.verification_submitted_at.asc()).first()
    
    return jsonify({
        'success': True,
        'message': f'{user.full_name} has been verified',
        'next_user_id': next_pending.id if next_pending else None
    })


@admin_bp.route('/verification/<int:user_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_verification(user_id):
    """Reject a user's verification"""
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    notes = data.get('notes', '')
    
    if not notes:
        return jsonify({'error': 'Notes are required for rejection'}), 400
    
    user.verification_status = 'rejected'
    user.verification_notes = notes
    db.session.commit()
    
    next_pending = User.query.filter(
        User.verification_status == 'pending',
        User.id != user_id
    ).order_by(User.verification_submitted_at.asc()).first()
    
    return jsonify({
        'success': True,
        'message': f'{user.full_name} verification has been rejected',
        'next_user_id': next_pending.id if next_pending else None
    })
