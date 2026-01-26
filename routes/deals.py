"""
Deals Routes - Investment marketplace
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from app import db
from models import InvestmentDeal, DealInterest, DealStatus
from facebook_page import share_deal, is_facebook_configured
from utils.ads import get_deal_inline_ad


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

deals_bp = Blueprint('deals', __name__, url_prefix='/deals')


@deals_bp.route('/')
@login_required
def list_deals():
    """List active investment deals with advanced filtering and sorting"""
    # Filter parameters
    deal_type = request.args.get('type')
    min_investment = request.args.get('min_investment', type=int)
    max_investment = request.args.get('max_investment', type=int)
    sort_by = request.args.get('sort', 'featured')
    
    query = InvestmentDeal.query.filter(InvestmentDeal.status == 'active')
    
    if deal_type:
        query = query.filter(InvestmentDeal.deal_type == deal_type)
    
    if min_investment:
        query = query.filter(InvestmentDeal.minimum_investment >= min_investment)
    
    if max_investment:
        query = query.filter(InvestmentDeal.minimum_investment <= max_investment)
    
    # Sorting options
    if sort_by == 'newest':
        query = query.order_by(InvestmentDeal.created_at.desc())
    elif sort_by == 'min_low':
        query = query.order_by(InvestmentDeal.minimum_investment.asc())
    elif sort_by == 'min_high':
        query = query.order_by(InvestmentDeal.minimum_investment.desc())
    elif sort_by == 'popular':
        query = query.order_by(InvestmentDeal.interest_count.desc())
    else:
        query = query.order_by(InvestmentDeal.is_featured.desc(), InvestmentDeal.created_at.desc())
    
    deals = query.all()
    
    # Get user's interests
    user_interests = []
    if current_user.is_authenticated:
        interests = DealInterest.query.filter_by(user_id=current_user.id).all()
        user_interests = [i.deal_id for i in interests]
    
    # Deal types for filter
    deal_types = [
        ('real_estate', 'Real Estate'),
        ('fund', 'Fund'),
        ('syndicate', 'Syndicate'),
        ('practice', 'Practice Opportunity'),
    ]
    
    # Get inline ad for deals page
    try:
        deal_ad = get_deal_inline_ad(user_id=current_user.id if current_user.is_authenticated else None)
    except:
        deal_ad = None
    
    return render_template('deals/list.html',
                         deals=deals,
                         user_interests=user_interests,
                         deal_types=deal_types,
                         selected_type=deal_type,
                         sort_by=sort_by,
                         min_investment=min_investment,
                         max_investment=max_investment,
                         deal_ad=deal_ad)


@deals_bp.route('/<int:deal_id>')
@login_required
def view_deal(deal_id):
    """View deal details"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    # Increment view count
    deal.view_count += 1
    db.session.commit()
    
    # Check if user has expressed interest
    user_interest = DealInterest.query.filter_by(
        deal_id=deal_id,
        user_id=current_user.id
    ).first()
    
    # Get interest count for display
    interest_count = DealInterest.query.filter_by(deal_id=deal_id).count()
    
    return render_template('deals/detail.html',
                         deal=deal,
                         user_interest=user_interest,
                         interest_count=interest_count)


@deals_bp.route('/<int:deal_id>/interest', methods=['POST'])
@login_required
def express_interest(deal_id):
    """Express interest in a deal"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    # Check if already interested
    existing = DealInterest.query.filter_by(
        deal_id=deal_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already expressed interest'}), 400
    
    data = request.get_json()
    
    interest = DealInterest(
        deal_id=deal_id,
        user_id=current_user.id,
        investment_amount=data.get('investment_amount'),
        message=data.get('message')
    )
    
    deal.interest_count += 1
    current_user.add_points(20)
    
    db.session.add(interest)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Interest submitted! The sponsor will contact you.'
    })


@deals_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_deal():
    """Submit a new deal for review"""
    if request.method == 'GET':
        return render_template('deals/submit.html')
    
    # Process submission
    deal = InvestmentDeal(
        title=request.form.get('title'),
        description=request.form.get('description'),
        deal_type=request.form.get('deal_type'),
        minimum_investment=float(request.form.get('minimum_investment', 0)),
        target_raise=float(request.form.get('target_raise')) if request.form.get('target_raise') else None,
        projected_return=request.form.get('projected_return'),
        investment_term=request.form.get('investment_term'),
        location=request.form.get('location'),
        sponsor_name=request.form.get('sponsor_name'),
        sponsor_bio=request.form.get('sponsor_bio'),
        sponsor_contact=request.form.get('sponsor_contact'),
        status=DealStatus.REVIEW
    )
    
    db.session.add(deal)
    db.session.commit()
    
    flash('Deal submitted for review! We\'ll notify you once it\'s approved.', 'success')
    return redirect(url_for('deals.list_deals'))


@deals_bp.route('/<int:deal_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_deal(deal_id):
    """Approve a deal and make it active (admin only)"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    if deal.status == DealStatus.ACTIVE:
        flash('Deal is already active', 'info')
        return redirect(url_for('deals.view_deal', deal_id=deal_id))
    
    deal.status = DealStatus.ACTIVE
    db.session.commit()
    
    # Auto-post to Facebook
    if is_facebook_configured():
        fb_result = share_deal(deal)
        if fb_result.get('success'):
            flash(f'Deal "{deal.title}" approved and shared to Facebook!', 'success')
        else:
            flash(f'Deal "{deal.title}" approved! (Facebook post failed)', 'warning')
    else:
        flash(f'Deal "{deal.title}" is now active!', 'success')
    
    return redirect(url_for('deals.view_deal', deal_id=deal_id))


@deals_bp.route('/admin')
@login_required
@admin_required
def admin_deals():
    """Admin view of all deals including pending"""
    pending = InvestmentDeal.query.filter_by(status=DealStatus.REVIEW).order_by(
        InvestmentDeal.created_at.desc()
    ).all()
    
    active = InvestmentDeal.query.filter_by(status=DealStatus.ACTIVE).order_by(
        InvestmentDeal.created_at.desc()
    ).all()
    
    closed = InvestmentDeal.query.filter_by(status=DealStatus.CLOSED).order_by(
        InvestmentDeal.created_at.desc()
    ).all()
    
    return render_template('deals/admin.html',
                         pending=pending,
                         active=active,
                         closed=closed)


@deals_bp.route('/<int:deal_id>/share-facebook', methods=['POST'])
@login_required
@admin_required
def share_to_facebook(deal_id):
    """Manually share a deal to Facebook (admin only)"""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    if not is_facebook_configured():
        flash('Facebook integration not configured', 'error')
        return redirect(url_for('deals.view_deal', deal_id=deal_id))
    
    fb_result = share_deal(deal)
    if fb_result.get('success'):
        flash(f'Deal shared to Facebook successfully!', 'success')
    else:
        flash(f'Facebook post failed: {fb_result.get("error", "unknown")}', 'error')
    
    return redirect(url_for('deals.admin_deals'))
