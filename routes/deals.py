"""
Deals Routes - Investment marketplace
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import InvestmentDeal, DealInterest, DealStatus

deals_bp = Blueprint('deals', __name__, url_prefix='/deals')


@deals_bp.route('/')
@login_required
def list_deals():
    """List active investment deals"""
    # Filter by type if specified
    deal_type = request.args.get('type')
    
    query = InvestmentDeal.query.filter(InvestmentDeal.status == 'active')
    
    if deal_type:
        query = query.filter(InvestmentDeal.deal_type == deal_type)
    
    deals = query.order_by(
        InvestmentDeal.is_featured.desc(),
        InvestmentDeal.created_at.desc()
    ).all()
    
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
    
    return render_template('deals/list.html',
                         deals=deals,
                         user_interests=user_interests,
                         deal_types=deal_types,
                         selected_type=deal_type)


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
