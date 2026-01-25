"""Facebook Webhook Routes - Receive and process messages from Facebook"""
import os
import logging
import hashlib
import hmac
import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

FACEBOOK_WEBHOOK_SECRET = os.environ.get('FACEBOOK_WEBHOOK_SECRET')
if not FACEBOOK_WEBHOOK_SECRET:
        raise ValueError("FACEBOOK_WEBHOOK_SECRET environment variable is not set")

def verify_facebook_webhook(data, signature):
    """Verify that the webhook request came from Facebook"""
    if not FACEBOOK_WEBHOOK_SECRET:
        logger.warning("FACEBOOK_WEBHOOK_SECRET not configured!")
        return False

    try:
        hash_algorithm, hash_value = signature.split('=')
        if hash_algorithm != 'sha1':
            logger.warning(f"Unexpected signature algorithm: {hash_algorithm}")
            return False

        expected_hash = hmac.new(
            FACEBOOK_WEBHOOK_SECRET.encode(),
            data,
            hashlib.sha1
        ).hexdigest()

        return hmac.compare_digest(expected_hash, hash_value)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


@webhooks_bp.route('/facebook', methods=['GET'])
def facebook_webhook_verify():
    """Verify webhook with Facebook - GET request"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    verify_token = os.environ.get('FACEBOOK_WEBHOOK_VERIFY_TOKEN')
    if not verify_token:
        raise ValueError("FACEBOOK_WEBHOOK_VERIFY_TOKEN environment variable is not set")
    if mode == 'subscribe' and token == verify_token:
        logger.info("Facebook webhook verified successfully!")
        return challenge, 200
    else:
        logger.warning("Webhook verification failed!")
        return 'Verification failed', 403


@webhooks_bp.route('/facebook', methods=['POST'])
def facebook_webhook_receive():
    """Receive messages and feed posts from Facebook - POST request"""
    try:
        signature = request.headers.get('X-Hub-Signature', '')
        if not verify_facebook_webhook(request.data, signature):
            logger.warning("Invalid webhook signature!")
            return jsonify({'error': 'Invalid signature'}), 403

        data = request.get_json()
        logger.info(f"Facebook webhook received: {json.dumps(data)[:500]}")

        if not data:
            logger.warning("Empty webhook data")
            return jsonify({'error': 'No data'}), 400

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                # Handle Messenger messages
                for messaging in entry.get('messaging', []):
                    process_messaging_event(messaging)
                
                # Handle Page feed changes (posts on the Facebook Page)
                for change in entry.get('changes', []):
                    process_page_feed_change(change, entry.get('id'))

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"Error processing Facebook webhook: {e}")
        return jsonify({'error': str(e)}), 500


def process_messaging_event(messaging):
    """Process individual messaging events from Facebook"""
    sender_id = messaging.get('sender', {}).get('id')
    recipient_id = messaging.get('recipient', {}).get('id')
    timestamp = messaging.get('timestamp')

    logger.info(f"Processing message from {sender_id} to {recipient_id}")

    if 'message' in messaging:
        message_data = messaging['message']
        message_id = message_data.get('mid')
        text = message_data.get('text')

        if text:
            logger.info(f"Message from {sender_id}: {text}")
            send_read_receipt(sender_id)
            process_message_for_platform(sender_id, text)


def send_read_receipt(sender_id):
    """Send read receipt to user on Facebook"""
    import requests

    facebook_page_access_token = os.environ.get('FACEBOOK_PAGE_ACCESS_TOKEN', '')
    if not facebook_page_access_token:
        logger.warning("FACEBOOK_PAGE_ACCESS_TOKEN not configured!")
        return

    try:
        url = "https://graph.facebook.com/v18.0/me/messages"
        payload = {
            'recipient': {'id': sender_id},
            'sender_action': 'mark_seen',
            'access_token': facebook_page_access_token
        }
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logger.warning(f"Failed to send read receipt: {response.text}")
    except Exception as e:
        logger.error(f"Error sending read receipt: {e}")


def process_message_for_platform(sender_id, message_text):
    """Process incoming Facebook message and create post on platform"""
    try:
        logger.info(f"Processing message for platform from {sender_id}: {message_text}")
        
        # Try to find user by facebook_id (from OAuth login)
        user = User.query.filter_by(facebook_id=str(sender_id)).first()
        
        # Fallback to replit_id format
        if not user:
            user = User.query.filter_by(replit_id=f"facebook_{sender_id}").first()

        if not user:
            logger.info(f"No user found for Facebook sender {sender_id}")
            return

        from models import Post

        post = Post(
            user_id=user.id,
            content=message_text,
            post_type='text'
        )
        db.session.add(post)
        db.session.commit()

        logger.info(f"Created post from Facebook message for user {user.id}")

    except Exception as e:
        logger.error(f"Error processing message for platform: {e}")
        db.session.rollback()


def process_page_feed_change(change, page_id):
    """Process Facebook Page feed changes (new posts on the page)"""
    try:
        field = change.get('field')
        value = change.get('value', {})
        
        logger.info(f"Processing page feed change: field={field}, value={json.dumps(value)[:300]}")
        
        if field != 'feed':
            return
        
        item = value.get('item')
        verb = value.get('verb')
        
        # Only process new posts (not edits, deletes, or comments)
        if item != 'status' and item != 'photo' and item != 'video':
            logger.info(f"Ignoring non-post item: {item}")
            return
        
        if verb != 'add':
            logger.info(f"Ignoring verb: {verb}")
            return
        
        message = value.get('message', '')
        post_id = value.get('post_id')
        from_id = value.get('from', {}).get('id')
        from_name = value.get('from', {}).get('name', 'Facebook User')
        
        if not message:
            logger.info("No message content in post, skipping")
            return
        
        # Check if this post was already synced (avoid duplicates)
        from models import Post
        existing = Post.query.filter_by(facebook_post_id=post_id).first() if post_id else None
        if existing:
            logger.info(f"Post {post_id} already exists on platform")
            return
        
        # Try to find the user who posted (by their Facebook ID)
        user = None
        if from_id:
            user = User.query.filter_by(facebook_id=str(from_id)).first()
        
        # If no matching user, create the post under a system/admin account or skip
        if not user:
            # Find an admin user to attribute the post to
            user = User.query.filter_by(is_admin=True).first()
            if not user:
                logger.warning(f"No admin user found to attribute Facebook post from {from_name}")
                return
            
            # Prefix message to indicate it's from Facebook
            message = f"📘 From Facebook ({from_name}):\n\n{message}"
        
        # Create the post on the platform
        post = Post(
            user_id=user.id,
            content=message,
            post_type='text',
            facebook_post_id=post_id
        )
        db.session.add(post)
        db.session.commit()
        
        logger.info(f"Created post from Facebook Page: {post.id} (FB: {post_id})")
        
    except Exception as e:
        logger.error(f"Error processing page feed change: {e}")
        db.session.rollback()
