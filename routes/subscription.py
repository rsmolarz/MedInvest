"""
Subscription Routes - Premium membership with Stripe integration
Integration: stripe connector
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from models import Subscription, Payment, SubscriptionTier, User
import logging

logger = logging.getLogger(__name__)

subscription_bp = Blueprint('subscription', __name__, url_prefix='/subscription')


def get_stripe():
    """Get Stripe client - lazy import to avoid startup errors"""
    try:
        from utils.stripe_client import get_stripe_client
        return get_stripe_client()
    except Exception as e:
        logger.warning(f"Stripe not available: {e}")
        return None


@subscription_bp.route('/pricing')
def pricing():
    """Display pricing page with Stripe prices"""
    from utils.stripe_client import SUBSCRIPTION_TIERS, get_publishable_key
    
    try:
        publishable_key = get_publishable_key()
    except:
        publishable_key = None
    
    return render_template('subscription/pricing.html',
                         tiers=SUBSCRIPTION_TIERS,
                         stripe_publishable_key=publishable_key)


@subscription_bp.route('/checkout/<tier>/<interval>')
@login_required
def checkout(tier, interval):
    """Create Stripe checkout session"""
    if tier not in ['pro', 'elite']:
        flash('Invalid subscription tier', 'error')
        return redirect(url_for('subscription.pricing'))
    
    if interval not in ['month', 'year']:
        flash('Invalid billing interval', 'error')
        return redirect(url_for('subscription.pricing'))
    
    try:
        stripe = get_stripe()
        if not stripe:
            flash('Payment system temporarily unavailable. Please try again later.', 'warning')
            return redirect(url_for('subscription.pricing'))
        
        prices = stripe.Price.search(
            query=f"metadata['tier']:'{tier}' AND metadata['interval']:'{interval}'"
        )
        
        if not prices.data:
            products = stripe.Product.search(query=f"metadata['tier']:'{tier}'")
            if products.data:
                all_prices = stripe.Price.list(product=products.data[0].id, active=True)
                for p in all_prices.data:
                    if p.recurring and p.recurring.interval == interval:
                        prices.data = [p]
                        break
        
        if not prices.data:
            flash('Subscription plan not found. Please contact support.', 'error')
            return redirect(url_for('subscription.pricing'))
        
        price = prices.data[0]
        
        customer_id = getattr(current_user, 'stripe_customer_id', None)
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={'user_id': str(current_user.id)}
            )
            customer_id = customer.id
            current_user.stripe_customer_id = customer_id
            db.session.commit()
        
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price.id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('subscription.pricing', _external=True),
            metadata={
                'user_id': str(current_user.id),
                'tier': tier,
                'interval': interval
            }
        )
        
        return redirect(checkout_session.url)
        
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        flash('Unable to process checkout. Please try again.', 'error')
        return redirect(url_for('subscription.pricing'))


@subscription_bp.route('/success')
@login_required
def success():
    """Handle successful checkout"""
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            stripe = get_stripe()
            if stripe:
                session = stripe.checkout.Session.retrieve(session_id)
                subscription_id = session.subscription
                
                if subscription_id:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    
                    tier = session.metadata.get('tier', 'pro')
                    interval = session.metadata.get('interval', 'month')
                    
                    db_subscription = Subscription(
                        user_id=current_user.id,
                        tier=tier,
                        stripe_subscription_id=subscription_id,
                        stripe_price_id=sub['items']['data'][0]['price']['id'] if sub.get('items') else None,
                        amount=sub['items']['data'][0]['price']['unit_amount'] / 100 if sub.get('items') else 0,
                        interval=interval,
                        status='active',
                        current_period_start=datetime.fromtimestamp(sub['current_period_start']),
                        current_period_end=datetime.fromtimestamp(sub['current_period_end'])
                    )
                    db.session.add(db_subscription)
                    
                    if tier == 'elite':
                        current_user.subscription_tier = SubscriptionTier.ELITE.value
                    else:
                        current_user.subscription_tier = SubscriptionTier.PRO.value
                    
                    current_user.subscription_ends_at = datetime.fromtimestamp(sub['current_period_end'])
                    current_user.add_points(200)
                    
                    db.session.commit()
        except Exception as e:
            logger.error(f"Success page error: {e}")
    
    flash('Welcome to MedInvest Premium! Your subscription is now active.', 'success')
    return redirect(url_for('subscription.manage'))


@subscription_bp.route('/manage')
@login_required
def manage():
    """Manage subscription"""
    active_subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).order_by(Subscription.created_at.desc()).first()
    
    from utils.stripe_client import SUBSCRIPTION_TIERS
    
    return render_template('subscription/manage.html',
                         subscription=active_subscription,
                         tiers=SUBSCRIPTION_TIERS)


@subscription_bp.route('/portal')
@login_required
def portal():
    """Redirect to Stripe customer portal"""
    try:
        stripe = get_stripe()
        if not stripe:
            flash('Billing portal temporarily unavailable.', 'warning')
            return redirect(url_for('subscription.manage'))
        
        customer_id = getattr(current_user, 'stripe_customer_id', None)
        if not customer_id:
            flash('No billing account found.', 'warning')
            return redirect(url_for('subscription.manage'))
        
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=url_for('subscription.manage', _external=True)
        )
        
        return redirect(portal_session.url)
        
    except Exception as e:
        logger.error(f"Portal error: {e}")
        flash('Unable to access billing portal.', 'error')
        return redirect(url_for('subscription.manage'))


@subscription_bp.route('/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel subscription"""
    try:
        stripe = get_stripe()
        
        active_sub = Subscription.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).first()
        
        if active_sub and active_sub.stripe_subscription_id and stripe:
            stripe.Subscription.modify(
                active_sub.stripe_subscription_id,
                cancel_at_period_end=True
            )
            active_sub.cancel_at_period_end = True
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Subscription will be cancelled at the end of your billing period.'
        })
        
    except Exception as e:
        logger.error(f"Cancel error: {e}")
        return jsonify({
            'success': False,
            'message': 'Unable to cancel subscription. Please try again.'
        }), 500


@subscription_bp.route('/api/prices')
def api_prices():
    """API endpoint for subscription prices"""
    from utils.stripe_client import get_subscription_prices
    
    try:
        prices = get_subscription_prices()
        return jsonify({'prices': prices})
    except Exception as e:
        logger.error(f"API prices error: {e}")
        return jsonify({'prices': [], 'error': str(e)}), 500


@subscription_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks for subscription events"""
    import os
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        stripe = get_stripe()
        if not stripe:
            return jsonify({'error': 'Stripe not configured'}), 500
        
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            event = stripe.Event.construct_from(request.get_json(), stripe.api_key)
        
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'customer.subscription.updated':
            handle_subscription_updated(data)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data)
        elif event_type == 'invoice.payment_succeeded':
            handle_payment_succeeded(data)
        elif event_type == 'invoice.payment_failed':
            handle_payment_failed(data)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 400


def handle_subscription_updated(subscription_data):
    """Handle subscription update from Stripe"""
    stripe_sub_id = subscription_data.get('id')
    status = subscription_data.get('status')
    
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
    if sub:
        sub.status = status
        if subscription_data.get('cancel_at_period_end'):
            sub.cancel_at_period_end = True
        if subscription_data.get('current_period_end'):
            sub.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
        db.session.commit()
        logger.info(f"Updated subscription {stripe_sub_id} to status {status}")


def handle_subscription_deleted(subscription_data):
    """Handle subscription cancellation from Stripe"""
    stripe_sub_id = subscription_data.get('id')
    
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
    if sub:
        sub.status = 'cancelled'
        user = User.query.get(sub.user_id)
        if user:
            user.subscription_tier = 'free'
            user.subscription_ends_at = None
        db.session.commit()
        logger.info(f"Cancelled subscription {stripe_sub_id}")


def handle_payment_succeeded(invoice_data):
    """Handle successful payment"""
    from models import Payment
    
    customer_id = invoice_data.get('customer')
    amount = invoice_data.get('amount_paid', 0) / 100
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        payment = Payment(
            user_id=user.id,
            amount=amount,
            stripe_payment_id=invoice_data.get('id'),
            status='completed',
            payment_method='stripe'
        )
        db.session.add(payment)
        db.session.commit()
        logger.info(f"Recorded payment of ${amount} for user {user.id}")


def handle_payment_failed(invoice_data):
    """Handle failed payment"""
    customer_id = invoice_data.get('customer')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        logger.warning(f"Payment failed for user {user.id}")
