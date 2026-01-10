"""
Admin Routes - Platform administration
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
from app import db
from models import (User, Post, Room, ExpertAMA, AMAStatus, InvestmentDeal, 
                   DealStatus, Course, Event, SubscriptionTier)

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
        'premium_users': User.query.filter(User.subscription_tier == SubscriptionTier.PREMIUM).count(),
        'new_users_week': User.query.filter(User.created_at >= week_ago).count(),
        'new_users_month': User.query.filter(User.created_at >= month_ago).count(),
        'total_posts': Post.query.count(),
        'posts_week': Post.query.filter(Post.created_at >= week_ago).count(),
        'active_deals': InvestmentDeal.query.filter(InvestmentDeal.status == DealStatus.ACTIVE).count(),
        'pending_deals': InvestmentDeal.query.filter(InvestmentDeal.status == DealStatus.REVIEW).count(),
        'upcoming_amas': ExpertAMA.query.filter(ExpertAMA.status == AMAStatus.SCHEDULED).count(),
        'total_courses': Course.query.filter_by(is_published=True).count(),
        'total_events': Event.query.filter_by(is_published=True).count(),
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
