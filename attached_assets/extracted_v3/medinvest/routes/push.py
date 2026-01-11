"""
Push Notifications Routes - Web Push API implementation
"""
import json
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from app import db
from models import (
    PushSubscription, NotificationPreference, Notification, 
    NotificationType, User
)

push_bp = Blueprint('push', __name__, url_prefix='/push')


# =============================================================================
# VAPID KEYS (Generate once and store in environment variables)
# =============================================================================
# Generate with: from py_vapid import Vapid; v = Vapid(); v.generate_keys()
# Or use: npx web-push generate-vapid-keys

def get_vapid_keys():
    """Get VAPID keys from environment or generate placeholder"""
    public_key = os.environ.get('VAPID_PUBLIC_KEY')
    private_key = os.environ.get('VAPID_PRIVATE_KEY')
    
    # Fallback keys for development (replace in production!)
    if not public_key:
        public_key = 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U'
    if not private_key:
        private_key = 'UUxI4O8-FbRouADVXBXFuGdF0iMxKcHKiQBPi6jPkfQ'
    
    return public_key, private_key


# =============================================================================
# SUBSCRIPTION ENDPOINTS
# =============================================================================

@push_bp.route('/vapid-public-key')
@login_required
def get_public_key():
    """Get VAPID public key for client-side subscription"""
    public_key, _ = get_vapid_keys()
    return jsonify({'publicKey': public_key})


@push_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    """Subscribe to push notifications"""
    data = request.get_json()
    
    if not data or 'subscription' not in data:
        return jsonify({'error': 'Invalid subscription data'}), 400
    
    subscription = data['subscription']
    endpoint = subscription.get('endpoint')
    keys = subscription.get('keys', {})
    
    if not endpoint:
        return jsonify({'error': 'Missing endpoint'}), 400
    
    # Check if subscription already exists
    existing = PushSubscription.query.filter_by(
        user_id=current_user.id,
        endpoint=endpoint
    ).first()
    
    if existing:
        # Update existing subscription
        existing.p256dh_key = keys.get('p256dh')
        existing.auth_key = keys.get('auth')
        existing.is_active = True
        existing.last_used = datetime.utcnow()
        existing.failed_count = 0
    else:
        # Create new subscription
        push_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh_key=keys.get('p256dh'),
            auth_key=keys.get('auth'),
            device_name=data.get('deviceName', 'Unknown Device'),
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(push_sub)
    
    # Ensure notification preferences exist
    if not current_user.notification_prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Successfully subscribed to push notifications'
    })


@push_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Unsubscribe from push notifications"""
    data = request.get_json()
    endpoint = data.get('endpoint') if data else None
    
    if endpoint:
        # Unsubscribe specific endpoint
        PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=endpoint
        ).delete()
    else:
        # Unsubscribe all
        PushSubscription.query.filter_by(user_id=current_user.id).delete()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Successfully unsubscribed from push notifications'
    })


@push_bp.route('/subscriptions')
@login_required
def list_subscriptions():
    """List user's active push subscriptions (devices)"""
    subscriptions = PushSubscription.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return jsonify({
        'subscriptions': [{
            'id': sub.id,
            'device_name': sub.device_name,
            'created_at': sub.created_at.isoformat(),
            'last_used': sub.last_used.isoformat() if sub.last_used else None
        } for sub in subscriptions]
    })


@push_bp.route('/subscriptions/<int:sub_id>', methods=['DELETE'])
@login_required
def delete_subscription(sub_id):
    """Delete a specific push subscription"""
    sub = PushSubscription.query.filter_by(
        id=sub_id,
        user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(sub)
    db.session.commit()
    
    return jsonify({'success': True})


# =============================================================================
# NOTIFICATION PREFERENCES
# =============================================================================

@push_bp.route('/preferences')
@login_required
def preferences_page():
    """Notification preferences page"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
    
    subscriptions = PushSubscription.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return render_template('push/preferences.html', 
                         prefs=prefs, 
                         subscriptions=subscriptions)


@push_bp.route('/preferences', methods=['POST'])
@login_required
def update_preferences():
    """Update notification preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
    
    # Update from form data
    prefs.push_enabled = request.form.get('push_enabled') == 'on'
    prefs.email_enabled = request.form.get('email_enabled') == 'on'
    
    # Push preferences
    prefs.push_mentions = request.form.get('push_mentions') == 'on'
    prefs.push_likes = request.form.get('push_likes') == 'on'
    prefs.push_comments = request.form.get('push_comments') == 'on'
    prefs.push_follows = request.form.get('push_follows') == 'on'
    prefs.push_replies = request.form.get('push_replies') == 'on'
    prefs.push_ama_reminders = request.form.get('push_ama_reminders') == 'on'
    prefs.push_deal_alerts = request.form.get('push_deal_alerts') == 'on'
    prefs.push_mentorship = request.form.get('push_mentorship') == 'on'
    prefs.push_system = request.form.get('push_system') == 'on'
    
    # Email preferences
    prefs.email_mentions = request.form.get('email_mentions') == 'on'
    prefs.email_likes = request.form.get('email_likes') == 'on'
    prefs.email_comments = request.form.get('email_comments') == 'on'
    prefs.email_follows = request.form.get('email_follows') == 'on'
    prefs.email_replies = request.form.get('email_replies') == 'on'
    prefs.email_ama_reminders = request.form.get('email_ama_reminders') == 'on'
    prefs.email_deal_alerts = request.form.get('email_deal_alerts') == 'on'
    prefs.email_weekly_digest = request.form.get('email_weekly_digest') == 'on'
    
    # Quiet hours
    prefs.quiet_hours_enabled = request.form.get('quiet_hours_enabled') == 'on'
    prefs.quiet_hours_start = int(request.form.get('quiet_hours_start', 22))
    prefs.quiet_hours_end = int(request.form.get('quiet_hours_end', 8))
    prefs.timezone = request.form.get('timezone', 'America/New_York')
    
    db.session.commit()
    
    from flask import flash
    flash('Notification preferences updated!', 'success')
    return render_template('push/preferences.html', prefs=prefs,
                         subscriptions=PushSubscription.query.filter_by(
                             user_id=current_user.id, is_active=True).all())


@push_bp.route('/preferences/api', methods=['GET', 'POST'])
@login_required
def preferences_api():
    """API endpoint for notification preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'GET':
        if not prefs:
            return jsonify({'push_enabled': True, 'email_enabled': True})
        
        return jsonify({
            'push_enabled': prefs.push_enabled,
            'email_enabled': prefs.email_enabled,
            'push_mentions': prefs.push_mentions,
            'push_likes': prefs.push_likes,
            'push_comments': prefs.push_comments,
            'push_follows': prefs.push_follows,
            'quiet_hours_enabled': prefs.quiet_hours_enabled
        })
    
    # POST - update preferences
    data = request.get_json()
    
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
    
    for key, value in data.items():
        if hasattr(prefs, key):
            setattr(prefs, key, value)
    
    db.session.commit()
    return jsonify({'success': True})


# =============================================================================
# SERVICE WORKER
# =============================================================================

@push_bp.route('/sw.js')
def service_worker():
    """Serve the service worker JavaScript"""
    return current_app.send_static_file('sw.js')


# =============================================================================
# SEND PUSH NOTIFICATION (Internal function)
# =============================================================================

def send_push_notification(user_id, title, body, url=None, icon=None, tag=None, data=None):
    """
    Send push notification to a user's subscribed devices
    
    Args:
        user_id: Target user ID
        title: Notification title
        body: Notification body text
        url: URL to open when clicked
        icon: Icon URL (optional)
        tag: Tag for notification grouping
        data: Additional data dict
    
    Returns:
        dict with success count and failures
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        print("pywebpush not installed. Install with: pip install pywebpush")
        return {'sent': 0, 'failed': 0, 'error': 'pywebpush not installed'}
    
    # Check user preferences
    prefs = NotificationPreference.query.filter_by(user_id=user_id).first()
    if prefs and not prefs.push_enabled:
        return {'sent': 0, 'failed': 0, 'skipped': 'Push disabled by user'}
    
    # Get user's subscriptions
    subscriptions = PushSubscription.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    if not subscriptions:
        return {'sent': 0, 'failed': 0, 'skipped': 'No active subscriptions'}
    
    public_key, private_key = get_vapid_keys()
    
    # Build notification payload
    payload = {
        'title': title,
        'body': body,
        'icon': icon or '/static/icons/icon-192.svg',
        'badge': '/static/icons/badge-72.svg',
        'tag': tag,
        'data': {
            'url': url or '/',
            **(data or {})
        },
        'requireInteraction': False,
        'actions': [
            {'action': 'open', 'title': 'Open'},
            {'action': 'dismiss', 'title': 'Dismiss'}
        ]
    }
    
    sent = 0
    failed = 0
    
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh_key,
                        'auth': sub.auth_key
                    }
                },
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims={
                    'sub': 'mailto:notifications@medinvest.com'
                }
            )
            
            sub.last_used = datetime.utcnow()
            sub.failed_count = 0
            sent += 1
            
        except WebPushException as e:
            failed += 1
            sub.failed_count += 1
            
            # Deactivate subscription after 3 failures
            if sub.failed_count >= 3:
                sub.is_active = False
            
            # Handle specific errors
            if e.response and e.response.status_code == 410:
                # Subscription expired/invalid - remove it
                sub.is_active = False
    
    db.session.commit()
    
    return {'sent': sent, 'failed': failed}


def should_send_push(user_id, notification_type):
    """Check if user wants push notifications for this type"""
    prefs = NotificationPreference.query.filter_by(user_id=user_id).first()
    
    if not prefs:
        return True  # Default to enabled
    
    if not prefs.push_enabled:
        return False
    
    # Map notification types to preferences
    type_map = {
        NotificationType.MENTION: prefs.push_mentions,
        NotificationType.LIKE: prefs.push_likes,
        NotificationType.COMMENT: prefs.push_comments,
        NotificationType.FOLLOW: prefs.push_follows,
        NotificationType.REPLY: prefs.push_replies,
        NotificationType.AMA_REMINDER: prefs.push_ama_reminders,
        NotificationType.AMA_ANSWER: prefs.push_ama_reminders,
        NotificationType.DEAL_ALERT: prefs.push_deal_alerts,
        NotificationType.MENTORSHIP_REQUEST: prefs.push_mentorship,
        NotificationType.MENTORSHIP_ACCEPTED: prefs.push_mentorship,
        NotificationType.SYSTEM: prefs.push_system,
    }
    
    return type_map.get(notification_type, True)


# =============================================================================
# TEST ENDPOINT (Development only)
# =============================================================================

@push_bp.route('/test', methods=['POST'])
@login_required
def test_notification():
    """Send a test push notification"""
    result = send_push_notification(
        user_id=current_user.id,
        title='Test Notification',
        body='This is a test push notification from MedInvest!',
        url='/notifications',
        tag='test'
    )
    
    return jsonify(result)
