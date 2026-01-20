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
                   AdCampaign, AdCreative, AdImpression, AdClick, MentorApplication, LTITool)
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


# ============== Facebook Sync Admin ==============

@admin_bp.route('/facebook-sync')
@login_required
@admin_required
def facebook_sync_status():
    """Facebook sync status and testing page - always fetches fresh token"""
    import requests
    import time
    import subprocess
    
    # Force fresh read of environment variables using subprocess
    def get_fresh_env(var_name):
        try:
            result = subprocess.run(
                ['printenv', var_name],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return os.environ.get(var_name)
    
    page_id = get_fresh_env('FACEBOOK_PAGE_ID')
    token = get_fresh_env('FACEBOOK_PAGE_ACCESS_TOKEN')
    
    status = {
        'configured': bool(page_id and token),
        'page_id': page_id,
        'token_present': bool(token),
        'token_valid': False,
        'page_name': None,
        'error': None,
        'webhook_url': request.host_url.rstrip('/') + '/webhooks/facebook',
        'last_checked': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    }
    
    # Test token validity
    if status['configured']:
        try:
            response = requests.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={'access_token': token, 'fields': 'name,id'},
                timeout=10
            )
            if response.ok:
                data = response.json()
                status['token_valid'] = True
                status['page_name'] = data.get('name')
            else:
                error_data = response.json()
                status['error'] = error_data.get('error', {}).get('message', 'Unknown error')
        except Exception as e:
            status['error'] = str(e)
    
    # Get recent posts that were shared to Facebook
    recent_posts = Post.query.filter(Post.facebook_post_id.isnot(None)).order_by(Post.created_at.desc()).limit(10).all()
    
    # Pass current timestamp for cache-busting refresh link
    return render_template('admin/facebook_sync.html', status=status, recent_posts=recent_posts, now=int(time.time()))


@admin_bp.route('/facebook-sync/test', methods=['POST'])
@login_required
@admin_required
def facebook_sync_test():
    """Test posting to Facebook"""
    from facebook_page import post_to_facebook, is_facebook_configured
    
    if not is_facebook_configured():
        return jsonify({'success': False, 'error': 'Facebook not configured'})
    
    message = request.form.get('message', 'Test post from MedInvest admin panel')
    result = post_to_facebook(message)
    
    return jsonify(result)


@admin_bp.route('/facebook-sync/validate')
@login_required  
@admin_required
def facebook_sync_validate():
    """Validate Facebook webhook subscription"""
    import requests
    from facebook_page import get_facebook_token
    
    # Check current webhook subscriptions
    try:
        app_id = os.environ.get('FACEBOOK_APP_ID')
        app_secret = os.environ.get('FACEBOOK_APP_SECRET')
        
        # Get app access token
        token_response = requests.get(
            'https://graph.facebook.com/oauth/access_token',
            params={
                'client_id': app_id,
                'client_secret': app_secret,
                'grant_type': 'client_credentials'
            },
            timeout=10
        )
        
        if not token_response.ok:
            return jsonify({'error': 'Failed to get app token', 'details': token_response.text})
        
        app_token = token_response.json().get('access_token')
        
        # Get current subscriptions
        subs_response = requests.get(
            f'https://graph.facebook.com/v18.0/{app_id}/subscriptions',
            params={'access_token': app_token},
            timeout=10
        )
        
        subscriptions = subs_response.json() if subs_response.ok else {'error': subs_response.text}
        
        return jsonify({
            'success': True,
            'subscriptions': subscriptions,
            'webhook_url': request.host_url.rstrip('/') + '/webhooks/facebook',
            'required_fields': ['feed', 'messages']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})


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
    """Spotlight session management (AMAs, Talks, Pitches, etc.)"""
    if request.method == 'POST':
        scheduled_str = request.form.get('scheduled_for')
        ticket_price_str = request.form.get('ticket_price', '0')
        
        ama = ExpertAMA(
            title=request.form.get('title'),
            expert_name=request.form.get('expert_name'),
            expert_title=request.form.get('expert_title'),
            expert_bio=request.form.get('expert_bio'),
            expert_image_url=request.form.get('expert_image_url'),
            description=request.form.get('description'),
            scheduled_for=datetime.fromisoformat(scheduled_str),
            duration_minutes=int(request.form.get('duration_minutes', 60)),
            is_premium_only=request.form.get('is_premium_only') == 'on',
            session_type=request.form.get('session_type', 'ama'),
            ticket_price=float(ticket_price_str) if ticket_price_str else None,
            youtube_live_url=request.form.get('youtube_live_url'),
            recording_url=request.form.get('recording_url'),
            sponsor_name=request.form.get('sponsor_name'),
            sponsor_logo_url=request.form.get('sponsor_logo_url'),
            status=AMAStatus.SCHEDULED
        )
        
        db.session.add(ama)
        db.session.commit()
        
        flash('Spotlight session created successfully!', 'success')
    
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


@admin_bp.route('/amas/<int:ama_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_ama(ama_id):
    """Edit a spotlight session"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    if request.method == 'POST':
        ama.title = request.form.get('title')
        ama.expert_name = request.form.get('expert_name')
        ama.expert_title = request.form.get('expert_title')
        ama.expert_bio = request.form.get('expert_bio')
        ama.expert_image_url = request.form.get('expert_image_url')
        ama.description = request.form.get('description')
        ama.scheduled_for = datetime.fromisoformat(request.form.get('scheduled_for'))
        ama.duration_minutes = int(request.form.get('duration_minutes', 60))
        ama.is_premium_only = request.form.get('is_premium_only') == 'on'
        ama.session_type = request.form.get('session_type', 'ama')
        ticket_price_str = request.form.get('ticket_price', '0')
        ama.ticket_price = float(ticket_price_str) if ticket_price_str else None
        ama.youtube_live_url = request.form.get('youtube_live_url')
        ama.recording_url = request.form.get('recording_url')
        ama.sponsor_name = request.form.get('sponsor_name')
        ama.sponsor_logo_url = request.form.get('sponsor_logo_url')
        
        status_str = request.form.get('status')
        if status_str:
            try:
                ama.status = AMAStatus(status_str)
            except ValueError:
                pass
        
        db.session.commit()
        flash('Session updated successfully!', 'success')
        return redirect(url_for('admin.manage_amas'))
    
    return render_template('admin/ama_edit.html', ama=ama)


@admin_bp.route('/amas/<int:ama_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_ama(ama_id):
    """Delete a spotlight session"""
    ama = ExpertAMA.query.get_or_404(ama_id)
    db.session.delete(ama)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Session deleted'})


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


@admin_bp.route('/posts')
@login_required
@admin_required
def manage_posts():
    """Post management - view and delete posts"""
    page = request.args.get('page', 1, type=int)
    room_id = request.args.get('room_id', type=int)
    search = request.args.get('search', '').strip()
    
    query = Post.query
    
    if room_id:
        query = query.filter(Post.room_id == room_id)
    
    if search:
        query = query.filter(Post.content.ilike(f'%{search}%'))
    
    posts = query.order_by(Post.created_at.desc()).paginate(page=page, per_page=20)
    rooms = Room.query.order_by(Room.name).all()
    
    return render_template('admin/posts.html', posts=posts, rooms=rooms, 
                          current_room_id=room_id, search=search)


@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    """Delete a post"""
    from models import PostMedia, PostVote, Comment, Bookmark, PostMention
    
    post = Post.query.get_or_404(post_id)
    
    # Delete related records
    PostMedia.query.filter_by(post_id=post_id).delete()
    PostVote.query.filter_by(post_id=post_id).delete()
    Comment.query.filter_by(post_id=post_id).delete()
    Bookmark.query.filter_by(post_id=post_id).delete()
    PostMention.query.filter_by(post_id=post_id).delete()
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post deleted successfully', 'success')
    return redirect(request.referrer or url_for('admin.manage_posts'))


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
@admin_required
def ads_dashboard():
    """Visual admin dashboard for managing ads"""
    
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
            course_url=request.form.get('course_url'),
            course_embed_code=request.form.get('course_embed_code'),
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
        course.course_url = request.form.get('course_url')
        course.course_embed_code = request.form.get('course_embed_code')
        lti_tool_id = request.form.get('lti_tool_id')
        course.lti_tool_id = int(lti_tool_id) if lti_tool_id else None
        course.lti_resource_link_id = request.form.get('lti_resource_link_id') or None
        course.is_published = request.form.get('is_published') == 'on'
        course.is_featured = request.form.get('is_featured') == 'on'
        
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))
    
    lti_tools = LTITool.query.order_by(LTITool.name).all()
    return render_template('admin/course_edit.html', course=course, lti_tools=lti_tools)


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


@admin_bp.route('/courses/<int:course_id>/modules', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_course_modules(course_id):
    """Manage course modules/curriculum"""
    from models import CourseModule
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        module = CourseModule(
            course_id=course_id,
            title=request.form.get('title'),
            description=request.form.get('description'),
            content=request.form.get('content'),
            video_url=request.form.get('video_url'),
            duration_minutes=int(request.form.get('duration_minutes', 0)) if request.form.get('duration_minutes') else 0,
            order_index=CourseModule.query.filter_by(course_id=course_id).count()
        )
        db.session.add(module)
        
        course.total_modules = CourseModule.query.filter_by(course_id=course_id).count() + 1
        course.total_duration_minutes = sum(m.duration_minutes or 0 for m in course.modules) + (module.duration_minutes or 0)
        
        db.session.commit()
        flash('Module added successfully!', 'success')
        return redirect(url_for('admin.manage_course_modules', course_id=course_id))
    
    modules = CourseModule.query.filter_by(course_id=course_id).order_by(CourseModule.order_index).all()
    return render_template('admin/course_modules.html', course=course, modules=modules)


@admin_bp.route('/courses/<int:course_id>/modules/<int:module_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_course_module(course_id, module_id):
    """Edit a course module"""
    from models import CourseModule
    module = CourseModule.query.get_or_404(module_id)
    course = Course.query.get_or_404(course_id)
    
    module.title = request.form.get('title')
    module.description = request.form.get('description')
    module.content = request.form.get('content')
    module.video_url = request.form.get('video_url')
    module.duration_minutes = int(request.form.get('duration_minutes', 0)) if request.form.get('duration_minutes') else 0
    
    course.total_duration_minutes = sum(m.duration_minutes or 0 for m in course.modules)
    
    db.session.commit()
    flash('Module updated successfully!', 'success')
    return redirect(url_for('admin.manage_course_modules', course_id=course_id))


@admin_bp.route('/courses/<int:course_id>/modules/<int:module_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course_module(course_id, module_id):
    """Delete a course module"""
    from models import CourseModule
    module = CourseModule.query.get_or_404(module_id)
    course = Course.query.get_or_404(course_id)
    
    db.session.delete(module)
    
    course.total_modules = CourseModule.query.filter_by(course_id=course_id).count() - 1
    course.total_duration_minutes = sum(m.duration_minutes or 0 for m in course.modules if m.id != module_id)
    
    db.session.commit()
    return jsonify({'success': True})


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
            is_featured=request.form.get('is_featured') == 'on',
            created_by_id=current_user.id,
            approval_status='approved'
        )
        
        db.session.add(event)
        db.session.commit()
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin.manage_events'))
    
    pending_events = Event.query.filter_by(approval_status='pending').order_by(Event.created_at.desc()).all()
    approved_events = Event.query.filter_by(approval_status='approved').order_by(Event.start_date.desc()).all()
    rejected_events = Event.query.filter_by(approval_status='rejected').order_by(Event.created_at.desc()).all()
    return render_template('admin/events.html', 
                         pending_events=pending_events,
                         approved_events=approved_events,
                         rejected_events=rejected_events)


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


@admin_bp.route('/events/<int:event_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_event(event_id):
    """Approve a pending event"""
    event = Event.query.get_or_404(event_id)
    event.approval_status = 'approved'
    event.is_published = True
    event.admin_notes = request.form.get('admin_notes', '')
    db.session.commit()
    
    flash(f'Event "{event.title}" approved and published!', 'success')
    return redirect(url_for('admin.manage_events'))


@admin_bp.route('/events/<int:event_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_event(event_id):
    """Reject a pending event"""
    event = Event.query.get_or_404(event_id)
    event.approval_status = 'rejected'
    event.is_published = False
    event.admin_notes = request.form.get('admin_notes', '')
    db.session.commit()
    
    flash(f'Event "{event.title}" rejected.', 'warning')
    return redirect(url_for('admin.manage_events'))


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


# ============== Mentor Management ==============

@admin_bp.route('/mentors')
@login_required
@admin_required
def manage_mentors():
    """Manage mentors and mentor applications"""
    tab = request.args.get('tab', 'applications')
    
    # Get pending mentor applications
    pending_applications = MentorApplication.query.filter_by(status='pending')\
        .order_by(MentorApplication.created_at.desc()).all()
    
    # Get approved mentors (users who have approved applications)
    approved_applications = MentorApplication.query.filter_by(status='approved')\
        .order_by(MentorApplication.reviewed_at.desc()).all()
    
    # Get rejected applications
    rejected_applications = MentorApplication.query.filter_by(status='rejected')\
        .order_by(MentorApplication.reviewed_at.desc()).all()
    
    stats = {
        'pending': len(pending_applications),
        'approved': len(approved_applications),
        'rejected': len(rejected_applications)
    }
    
    return render_template('admin/mentors.html',
                          tab=tab,
                          pending_applications=pending_applications,
                          approved_applications=approved_applications,
                          rejected_applications=rejected_applications,
                          stats=stats)


@admin_bp.route('/mentors/approve/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def approve_mentor_application(app_id):
    """Approve a mentor application"""
    application = MentorApplication.query.get_or_404(app_id)
    
    application.status = 'approved'
    application.reviewed_by_id = current_user.id
    application.reviewed_at = datetime.utcnow()
    application.admin_notes = request.form.get('notes', '')
    
    db.session.commit()
    
    flash(f'{application.user.full_name} has been approved as a mentor!', 'success')
    return redirect(url_for('admin.manage_mentors'))


@admin_bp.route('/mentors/reject/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def reject_mentor_application(app_id):
    """Reject a mentor application"""
    application = MentorApplication.query.get_or_404(app_id)
    
    application.status = 'rejected'
    application.reviewed_by_id = current_user.id
    application.reviewed_at = datetime.utcnow()
    application.admin_notes = request.form.get('notes', '')
    
    db.session.commit()
    
    flash(f'{application.user.full_name} mentor application has been rejected.', 'info')
    return redirect(url_for('admin.manage_mentors'))


@admin_bp.route('/mentors/revoke/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def revoke_mentor_status(app_id):
    """Revoke mentor status"""
    application = MentorApplication.query.get_or_404(app_id)
    
    application.status = 'rejected'
    application.admin_notes = f"Revoked by admin on {datetime.utcnow().strftime('%Y-%m-%d')}"
    
    db.session.commit()
    
    flash(f'{application.user.full_name} mentor status has been revoked.', 'warning')
    return redirect(url_for('admin.manage_mentors', tab='approved'))


# ============================================================================
# LTI TOOL MANAGEMENT
# ============================================================================

@admin_bp.route('/lti-tools')
@login_required
@admin_required
def manage_lti_tools():
    """List and manage LTI tools"""
    tools = LTITool.query.order_by(LTITool.created_at.desc()).all()
    return render_template('admin/lti_tools.html', tools=tools)


@admin_bp.route('/lti-tools/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_lti_tool():
    """Create a new LTI tool configuration"""
    from routes.lti import generate_rsa_key_pair, get_platform_issuer
    
    if request.method == 'POST':
        private_key, public_key = generate_rsa_key_pair()
        
        tool = LTITool(
            name=request.form.get('name'),
            description=request.form.get('description'),
            issuer=request.form.get('issuer'),
            client_id=request.form.get('client_id'),
            deployment_id=request.form.get('deployment_id'),
            oidc_auth_url=request.form.get('oidc_auth_url'),
            token_url=request.form.get('token_url'),
            jwks_url=request.form.get('jwks_url'),
            launch_url=request.form.get('launch_url'),
            public_key=public_key,
            private_key=private_key,
            is_active=request.form.get('is_active') == 'on'
        )
        
        db.session.add(tool)
        db.session.commit()
        
        flash('LTI tool created successfully!', 'success')
        return redirect(url_for('admin.view_lti_tool', tool_id=tool.id))
    
    platform_issuer = get_platform_issuer()
    return render_template('admin/lti_tool_form.html', tool=None, platform_issuer=platform_issuer)


@admin_bp.route('/lti-tools/<int:tool_id>')
@login_required
@admin_required
def view_lti_tool(tool_id):
    """View LTI tool details and platform configuration"""
    from routes.lti import get_platform_issuer
    
    tool = LTITool.query.get_or_404(tool_id)
    platform_issuer = get_platform_issuer()
    
    # Use the platform issuer as base URL to ensure correct public URLs
    platform_config = {
        'issuer': platform_issuer,
        'client_id': tool.client_id,
        'oidc_auth_url': f"{platform_issuer}/lti/auth/callback",
        'jwks_url': f"{platform_issuer}/lti/jwks.json",
        'launch_url': f"{platform_issuer}/lti/login/{tool.id}"
    }
    
    return render_template('admin/lti_tool_view.html', tool=tool, platform_config=platform_config)


@admin_bp.route('/lti-tools/<int:tool_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_lti_tool(tool_id):
    """Edit LTI tool configuration"""
    from routes.lti import get_platform_issuer
    
    tool = LTITool.query.get_or_404(tool_id)
    
    if request.method == 'POST':
        tool.name = request.form.get('name')
        tool.description = request.form.get('description')
        tool.issuer = request.form.get('issuer')
        tool.client_id = request.form.get('client_id')
        tool.deployment_id = request.form.get('deployment_id')
        tool.oidc_auth_url = request.form.get('oidc_auth_url')
        tool.token_url = request.form.get('token_url')
        tool.jwks_url = request.form.get('jwks_url')
        tool.launch_url = request.form.get('launch_url')
        tool.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('LTI tool updated successfully!', 'success')
        return redirect(url_for('admin.view_lti_tool', tool_id=tool.id))
    
    platform_issuer = get_platform_issuer()
    return render_template('admin/lti_tool_form.html', tool=tool, platform_issuer=platform_issuer)


@admin_bp.route('/lti-tools/<int:tool_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_lti_tool(tool_id):
    """Delete an LTI tool"""
    tool = LTITool.query.get_or_404(tool_id)
    
    Course.query.filter_by(lti_tool_id=tool_id).update({'lti_tool_id': None})
    
    db.session.delete(tool)
    db.session.commit()
    
    flash('LTI tool deleted', 'success')
    return redirect(url_for('admin.manage_lti_tools'))


@admin_bp.route('/lti-tools/<int:tool_id>/regenerate-keys', methods=['POST'])
@login_required
@admin_required
def regenerate_lti_keys(tool_id):
    """Regenerate RSA keys for an LTI tool"""
    from routes.lti import generate_rsa_key_pair
    
    tool = LTITool.query.get_or_404(tool_id)
    private_key, public_key = generate_rsa_key_pair()
    
    tool.private_key = private_key
    tool.public_key = public_key
    
    db.session.commit()
    
    flash('RSA keys regenerated. Update the JWKS in your LTI tool configuration.', 'warning')
    return redirect(url_for('admin.view_lti_tool', tool_id=tool.id))


@admin_bp.route('/bug-reports')
@login_required
@admin_required
def bug_reports():
    """View and manage user-submitted bug reports"""
    from models import BugReport
    
    status_filter = request.args.get('status', 'open')
    
    query = BugReport.query
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    reports = query.order_by(BugReport.created_at.desc()).all()
    
    stats = {
        'open': BugReport.query.filter_by(status='open').count(),
        'in_progress': BugReport.query.filter_by(status='in_progress').count(),
        'resolved': BugReport.query.filter_by(status='resolved').count(),
        'closed': BugReport.query.filter_by(status='closed').count()
    }
    
    return render_template('admin/bug_reports.html', 
                         reports=reports, 
                         status_filter=status_filter,
                         stats=stats)


@admin_bp.route('/bug-reports/<int:report_id>/update', methods=['POST'])
@login_required
@admin_required
def update_bug_report(report_id):
    """Update a bug report status"""
    from models import BugReport
    from datetime import datetime
    
    report = BugReport.query.get_or_404(report_id)
    
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '').strip()
    priority = request.form.get('priority')
    
    if new_status:
        report.status = new_status
        if new_status in ('resolved', 'closed'):
            report.resolved_by_id = current_user.id
            report.resolved_at = datetime.utcnow()
    
    if admin_notes:
        report.admin_notes = admin_notes
    
    if priority:
        report.priority = priority
    
    db.session.commit()
    flash('Bug report updated', 'success')
    
    return redirect(url_for('admin.bug_reports'))
