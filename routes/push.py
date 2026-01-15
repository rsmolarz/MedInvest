"""
Push Notification Routes
"""
import os
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import PushSubscription

push_bp = Blueprint('push', __name__, url_prefix='/push')

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')


@push_bp.route('/vapid-public-key')
def get_vapid_key():
    """Return the VAPID public key for client-side subscription"""
    return jsonify({'publicKey': VAPID_PUBLIC_KEY})


@push_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    """Subscribe to push notifications"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        
        if not all([endpoint, p256dh, auth]):
            return jsonify({'error': 'Invalid subscription data'}), 400
        
        existing = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=endpoint
        ).first()
        
        if existing:
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.is_active = True
        else:
            subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh_key=p256dh,
                auth_key=auth
            )
            db.session.add(subscription)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subscribed to push notifications'})
        
    except Exception as e:
        logging.error(f"Push subscription error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@push_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Unsubscribe from push notifications"""
    try:
        data = request.get_json()
        endpoint = data.get('endpoint') if data else None
        
        if endpoint:
            subscription = PushSubscription.query.filter_by(
                user_id=current_user.id,
                endpoint=endpoint
            ).first()
            if subscription:
                subscription.is_active = False
        else:
            PushSubscription.query.filter_by(user_id=current_user.id).update({'is_active': False})
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Unsubscribed from push notifications'})
        
    except Exception as e:
        logging.error(f"Push unsubscribe error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@push_bp.route('/status')
@login_required
def subscription_status():
    """Check if user has active push subscriptions"""
    count = PushSubscription.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).count()
    
    return jsonify({
        'subscribed': count > 0,
        'subscription_count': count
    })


@push_bp.route('/test', methods=['POST'])
@login_required
def test_push():
    """Send a test push notification to verify setup"""
    from push_service import send_push_notification
    
    subscriptions = PushSubscription.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    if not subscriptions:
        return jsonify({'success': False, 'error': 'No active subscriptions found. Please enable push notifications first.'}), 400
    
    success_count = 0
    for sub in subscriptions:
        try:
            result = send_push_notification(
                sub,
                title='MedInvest Test',
                body='Push notifications are working! You will now receive alerts for new messages, comments, and more.',
                url='/settings?tab=communication'
            )
            if result:
                success_count += 1
        except Exception as e:
            logging.error(f"Test push failed: {str(e)}")
    
    db.session.commit()
    
    if success_count > 0:
        return jsonify({'success': True, 'message': f'Test notification sent to {success_count} device(s)'})
    else:
        return jsonify({'success': False, 'error': 'Failed to send test notification. Please try re-enabling push notifications.'}), 500
