"""Facebook Webhook Routes - Receive and process messages from Facebook"""""
import os
import logging
import hashlib
import hmac
import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint for webhooks
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# Get webhook secret from environment
FACEBOOK_WEBHOOK_SECRET = os.environ.get('FACEBOOK_WEBHOOK_SECRET', '')


def verify_facebook_webhook(data, signature):
      """Verify that the webhook request came from Facebook
          
              Args:
                      data: Raw request body
                              signature: X-Hub-Signature header value
                                  
                                      Returns:
                                              bool: True if signature is valid
                                                  """""
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
      """Verify webhook with Facebook - GET request"""""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    verify_token = os.environ.get('FACEBOOK_WEBHOOK_VERIFY_TOKEN', '')

    if mode == 'subscribe' and token == verify_token:
              logger.info("Facebook webhook verified successfully!")
              return challenge, 200
    else:
              logger.warning(f"Webhook verification failed!")
              return 'Verification failed', 403


      @webhooks_bp.route('/facebook', methods=['POST'])
def facebook_webhook_receive():
      """Receive messages from Facebook - POST request"""""
    try:
              signature = request.headers.get('X-Hub-Signature', '')
              if not verify_facebook_webhook(request.data, signature):
                            logger.warning("Invalid webhook signature!")
                            return jsonify({'error': 'Invalid signature'}), 403

              data = request.get_json()

              if not data:
                            logger.warning("Empty webhook data")
                            return jsonify({'error': 'No data'}), 400

              if data.get('object') == 'page':
                            for entry in data.get('entry', []):
                                              for messaging in entry.get('messaging', []):
                                                                    process_messaging_event(messaging)

                      return jsonify({'status': 'ok'}), 200

        return jsonify({'status': 'ok'}), 200

except Exception as e:
        logger.error(f"Error processing Facebook webhook: {e}")
        return jsonify({'error': str(e)}), 500


def process_messaging_event(messaging):
      """Process individual messaging events from Facebook"""""
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
            """Send read receipt to user on Facebook"""""
            import requests

            facebook_page_access_token = os.environ.get('FACEBOOK_PAGE_ACCESS_TOKEN', '')
            if not facebook_page_access_token:
                      logger.warning("FACEBOOK_PAGE_ACCESS_TOKEN not configured!")
                      return

            try:
                      url = f"https://graph.facebook.com/v18.0/me/messages"
                      payload = {
                                    'recipient': {'id': sender_id},
                                    'sender_action': 'mark_seen',
                                    'access_token': facebook_page_access_token
                      }
                      response = requests.post(url, json=payload)
                      if response.status_code != 200:
                                    logger.warning(f"Failed to send read receipt: {response.text}")
            except Exception as e:
                      logger.error(f"Error s")
                      }
                )

def process_message_for_platform(sender_id, message_text):
              """Process incoming Facebook message and create post on platform"""""
              try:
                                logger.info(f"Processing message for platform from {sender_id}: {message_text}")

        # Get or create user from Facebook sender_id
                  user = User.query.filter_by(facebook_id=sender_id).first()

        if not user:
                              logger.info(f"Creating new user with Facebook ID {sender_id}")
                              # Create new user with Facebook ID
                              user = User(
                                                        facebook_id=sender_id,
                                                        username=f"fb_{sender_id}",
                                                        email=f"fb_{sender_id}@medmoneyincubator.com"
                              )
            db.session.add(user)
            db.session.commit()

        # Create a post/activity from the message
        from models import Post

        post = Post(
                              user_id=user.id,
                              title="Facebook Page Post",
                              content=message_text,
                              source="facebook_page"
        )
        db.session.add(post)
        db.session.commit()

        logger.info(f"Created post from Facebook message for user {user.id}")

except Exception as e:
        logger.error(f"Error processing message for platform: {e}")
        db.session.rollback()
        )
                              )