"""Webhook Management Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import Webhook, WebhookDelivery
from utils.webhook_manager import WebhookManager
import json

webhook_bp = Blueprint('webhook_admin', __name__, url_prefix='/admin/webhooks')


def admin_required(f):
    """Decorator to require admin access."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@webhook_bp.route('/')
@login_required
@admin_required
def list_webhooks():
    """List all webhooks."""
    webhooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    return render_template('admin/webhooks.html', webhooks=webhooks)


@webhook_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_webhook():
    """Create a new webhook."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        url = request.form.get('url', '').strip()
        events = request.form.getlist('events')
        
        if not url:
            flash('Webhook URL is required.', 'error')
            return redirect(url_for('webhook_admin.create_webhook'))
        
        webhook_id = WebhookManager.register_webhook(
            url=url,
            events=events,
            name=name
        )
        
        if webhook_id:
            flash('Webhook created successfully.', 'success')
            return redirect(url_for('webhook_admin.list_webhooks'))
        else:
            flash('Failed to create webhook.', 'error')
    
    available_events = [
        'user.created', 'user.updated', 'user.deleted',
        'post.created', 'post.updated', 'post.deleted',
        'comment.created', 'comment.deleted',
        'subscription.created', 'subscription.cancelled',
        'deal.created', 'deal.updated',
        'ama.scheduled', 'ama.started', 'ama.ended'
    ]
    
    return render_template('admin/webhook_form.html', 
                         webhook=None,
                         available_events=available_events)


@webhook_bp.route('/<int:webhook_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_webhook(webhook_id):
    """Edit a webhook."""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if request.method == 'POST':
        webhook.name = request.form.get('name', '').strip()
        webhook.url = request.form.get('url', '').strip()
        webhook.events = ','.join(request.form.getlist('events'))
        webhook.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Webhook updated successfully.', 'success')
        return redirect(url_for('webhook_admin.list_webhooks'))
    
    available_events = [
        'user.created', 'user.updated', 'user.deleted',
        'post.created', 'post.updated', 'post.deleted',
        'comment.created', 'comment.deleted',
        'subscription.created', 'subscription.cancelled',
        'deal.created', 'deal.updated',
        'ama.scheduled', 'ama.started', 'ama.ended'
    ]
    
    current_events = webhook.events.split(',') if webhook.events else []
    
    return render_template('admin/webhook_form.html',
                         webhook=webhook,
                         current_events=current_events,
                         available_events=available_events)


@webhook_bp.route('/<int:webhook_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_webhook(webhook_id):
    """Delete a webhook."""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    WebhookDelivery.query.filter_by(webhook_id=webhook_id).delete()
    db.session.delete(webhook)
    db.session.commit()
    
    flash('Webhook deleted.', 'success')
    return redirect(url_for('webhook_admin.list_webhooks'))


@webhook_bp.route('/<int:webhook_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_webhook(webhook_id):
    """Toggle webhook active status."""
    webhook = Webhook.query.get_or_404(webhook_id)
    webhook.is_active = not webhook.is_active
    db.session.commit()
    
    status = 'enabled' if webhook.is_active else 'disabled'
    flash(f'Webhook {status}.', 'success')
    return redirect(url_for('webhook_admin.list_webhooks'))


@webhook_bp.route('/<int:webhook_id>/deliveries')
@login_required
@admin_required
def webhook_deliveries(webhook_id):
    """View webhook delivery history."""
    webhook = Webhook.query.get_or_404(webhook_id)
    deliveries = WebhookDelivery.query.filter_by(
        webhook_id=webhook_id
    ).order_by(WebhookDelivery.created_at.desc()).limit(100).all()
    
    return render_template('admin/webhook_deliveries.html',
                         webhook=webhook,
                         deliveries=deliveries)


@webhook_bp.route('/<int:webhook_id>/test', methods=['POST'])
@login_required
@admin_required
def test_webhook(webhook_id):
    """Send a test webhook."""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    test_payload = {
        'event': 'test',
        'message': 'This is a test webhook from MedInvest',
        'webhook_id': webhook_id
    }
    
    WebhookManager.trigger_event('test', test_payload)
    flash('Test webhook sent.', 'success')
    return redirect(url_for('webhook_admin.webhook_deliveries', webhook_id=webhook_id))
