"""
Webhook System for External Integrations.
Handles webhook registration, delivery, and logging.
"""
import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
import requests
from app import db

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = [
    'user.created',
    'user.verified',
    'user.deleted',
    'subscription.created',
    'subscription.upgraded',
    'subscription.cancelled',
    'post.created',
    'post.deleted',
    'deal.created',
    'deal.interest',
    'ama.created',
    'ama.registered',
    'course.enrolled',
    'event.registered',
]

executor = ThreadPoolExecutor(max_workers=5)


class WebhookManager:
    """Manager for webhook operations."""
    
    @staticmethod
    def create_webhook(
        name: str,
        url: str,
        events: List[str],
        secret: str = None,
        is_active: bool = True
    ) -> Optional[int]:
        """Create a new webhook endpoint."""
        from models import Webhook
        
        valid_events = [e for e in events if e in SUPPORTED_EVENTS]
        if not valid_events:
            return None
        
        webhook = Webhook(
            name=name,
            url=url,
            events=','.join(valid_events),
            secret=secret,
            is_active=is_active,
            created_at=datetime.utcnow()
        )
        db.session.add(webhook)
        db.session.commit()
        
        return webhook.id
    
    @staticmethod
    def update_webhook(
        webhook_id: int,
        name: str = None,
        url: str = None,
        events: List[str] = None,
        secret: str = None,
        is_active: bool = None
    ) -> bool:
        """Update an existing webhook."""
        from models import Webhook
        
        webhook = Webhook.query.get(webhook_id)
        if not webhook:
            return False
        
        if name is not None:
            webhook.name = name
        if url is not None:
            webhook.url = url
        if events is not None:
            valid_events = [e for e in events if e in SUPPORTED_EVENTS]
            webhook.events = ','.join(valid_events)
        if secret is not None:
            webhook.secret = secret
        if is_active is not None:
            webhook.is_active = is_active
        
        db.session.commit()
        return True
    
    @staticmethod
    def delete_webhook(webhook_id: int) -> bool:
        """Delete a webhook."""
        from models import Webhook
        
        webhook = Webhook.query.get(webhook_id)
        if not webhook:
            return False
        
        db.session.delete(webhook)
        db.session.commit()
        return True
    
    @staticmethod
    def toggle_webhook(webhook_id: int) -> bool:
        """Toggle webhook active status."""
        from models import Webhook
        
        webhook = Webhook.query.get(webhook_id)
        if not webhook:
            return False
        
        webhook.is_active = not webhook.is_active
        db.session.commit()
        return True
    
    @staticmethod
    def get_webhooks_for_event(event: str) -> List:
        """Get all active webhooks subscribed to an event."""
        from models import Webhook
        
        webhooks = Webhook.query.filter_by(is_active=True).all()
        return [w for w in webhooks if event in (w.events or '').split(',')]
    
    @staticmethod
    def trigger_event(event: str, data: Dict) -> None:
        """Trigger an event and send to all subscribed webhooks."""
        webhooks = WebhookManager.get_webhooks_for_event(event)
        
        for webhook in webhooks:
            executor.submit(
                WebhookManager._deliver_webhook,
                webhook,
                event,
                data
            )
    
    @staticmethod
    def _deliver_webhook(webhook, event: str, data: Dict) -> None:
        """Deliver a webhook payload to an endpoint."""
        from models import WebhookDelivery
        
        payload = {
            'event': event,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-MedInvest-Event': event,
            'X-MedInvest-Delivery': str(datetime.utcnow().timestamp())
        }
        
        if webhook.secret:
            signature = WebhookManager._sign_payload(
                json.dumps(payload),
                webhook.secret
            )
            headers['X-MedInvest-Signature'] = signature
        
        start_time = datetime.utcnow()
        
        try:
            response = requests.post(
                webhook.url,
                json=payload,
                headers=headers,
                timeout=30
            )
            status_code = response.status_code
            response_body = response.text[:1000]
            success = 200 <= status_code < 300
            
        except requests.RequestException as e:
            status_code = 0
            response_body = str(e)
            success = False
            logger.error(f"Webhook delivery failed for {webhook.url}: {e}")
        
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            payload=json.dumps(payload)[:5000],
            status_code=status_code,
            response_body=response_body,
            duration_ms=duration_ms,
            success=success,
            created_at=start_time
        )
        
        try:
            db.session.add(delivery)
            webhook.last_triggered = start_time
            webhook.last_status = status_code
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log webhook delivery: {e}")
            db.session.rollback()
    
    @staticmethod
    def _sign_payload(payload: str, secret: str) -> str:
        """Sign a payload with HMAC-SHA256."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def test_webhook(webhook_id: int) -> Dict:
        """Send a test event to a webhook."""
        from models import Webhook
        
        webhook = Webhook.query.get(webhook_id)
        if not webhook:
            return {'success': False, 'error': 'Webhook not found'}
        
        test_data = {
            'message': 'This is a test webhook from MedInvest',
            'webhook_id': webhook_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            WebhookManager._deliver_webhook(webhook, 'test.ping', test_data)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_delivery_logs(webhook_id: int = None, limit: int = 50) -> List:
        """Get recent webhook delivery logs."""
        from models import WebhookDelivery
        
        query = WebhookDelivery.query
        
        if webhook_id:
            query = query.filter_by(webhook_id=webhook_id)
        
        return query.order_by(WebhookDelivery.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_stats() -> Dict:
        """Get webhook statistics."""
        from models import Webhook, WebhookDelivery
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        total_webhooks = Webhook.query.count()
        active_webhooks = Webhook.query.filter_by(is_active=True).count()
        
        deliveries_today = WebhookDelivery.query.filter(
            WebhookDelivery.created_at >= today
        ).count()
        
        successful = WebhookDelivery.query.filter_by(success=True).count()
        total = WebhookDelivery.query.count()
        success_rate = (successful / total * 100) if total > 0 else 100
        
        avg_response = db.session.query(
            db.func.avg(WebhookDelivery.duration_ms)
        ).scalar() or 0
        
        return {
            'total_webhooks': total_webhooks,
            'active_webhooks': active_webhooks,
            'deliveries_today': deliveries_today,
            'success_rate': success_rate,
            'avg_response_time': int(avg_response)
        }
