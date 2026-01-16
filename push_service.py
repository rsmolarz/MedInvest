"""
Web Push Notification Service
"""
import os
import logging
import json
from threading import Thread
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '').strip().replace('\\n', '').replace('\n', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '').strip().replace('\\n', '').replace('\n', '')
VAPID_CLAIMS = {"sub": "mailto:support@medmoneyincubator.com"}


def send_push_notification(subscription, title, body, url='/', icon=None, image=None):
    """
    Send a push notification to a single subscription.
    Returns True if successful, False otherwise.
    """
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logging.debug("VAPID keys not configured, skipping push notification")
        return False
    
    try:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key
            }
        }
        
        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "icon": icon or "/static/images/logo-icon.png",
            "image": image
        })
        
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
        
        return True
        
    except WebPushException as e:
        logging.warning(f"Push notification failed: {e}")
        if e.response and e.response.status_code in (404, 410):
            subscription.is_active = False
        return False
    except Exception as e:
        logging.error(f"Push notification error: {str(e)}")
        return False


def send_push_to_user(user_id, title, body, url='/', icon=None, image=None):
    """
    Send push notification to all of a user's active subscriptions.
    Runs in background thread to not block the request.
    """
    from app import app, db
    from models import PushSubscription
    from datetime import datetime
    
    def _send():
        with app.app_context():
            subscriptions = PushSubscription.query.filter_by(
                user_id=user_id, is_active=True
            ).all()
            
            for sub in subscriptions:
                success = send_push_notification(sub, title, body, url, icon, image)
                if success:
                    sub.last_used = datetime.utcnow()
            
            db.session.commit()
    
    thread = Thread(target=_send, daemon=True)
    thread.start()


def get_vapid_public_key():
    """Return the VAPID public key for client-side subscription"""
    return VAPID_PUBLIC_KEY
