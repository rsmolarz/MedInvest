"""
Subscription Routes - Premium membership
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from models import SubscriptionTier

subscription_bp = Blueprint('subscription', __name__, url_prefix='/subscription')


@subscription_bp.route('/pricing')
def pricing():
    """Display pricing page"""
    return render_template('subscription/pricing.html')


@subscription_bp.route('/checkout/<plan>')
@login_required
def checkout(plan):
    """Checkout for subscription"""
    if plan not in ['monthly', 'yearly']:
        flash('Invalid plan', 'error')
        return redirect(url_for('subscription.pricing'))
    
    # In production, integrate Stripe here
    # For now, simulate successful subscription
    flash('Payment integration coming soon! For demo, subscription activated.', 'info')
    
    # Demo: activate subscription
    current_user.subscription_tier = SubscriptionTier.PREMIUM
    if plan == 'monthly':
        current_user.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
    else:
        current_user.subscription_ends_at = datetime.utcnow() + timedelta(days=365)
    
    db.session.commit()
    
    return redirect(url_for('subscription.manage'))


@subscription_bp.route('/manage')
@login_required
def manage():
    """Manage subscription"""
    return render_template('subscription/manage.html')


@subscription_bp.route('/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel subscription"""
    current_user.subscription_tier = SubscriptionTier.FREE
    current_user.subscription_ends_at = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Subscription cancelled. You\'ll retain access until the end of your billing period.'
    })
