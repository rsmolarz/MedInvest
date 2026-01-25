"""
Market Inefficiency Agents (MIA) Integration Routes

Premium feature for connecting to marketinefficiencyagents.com
to receive market alerts and investment triggers in the feed.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import json
import logging

from app import db
from models import MIAConnection, MIAAlert

logger = logging.getLogger(__name__)

mia_bp = Blueprint('mia', __name__, url_prefix='/mia')


def premium_required(f):
    """Decorator requiring premium subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_premium:
            flash('This feature requires a premium subscription.', 'warning')
            return redirect(url_for('mia.upgrade'))
        return f(*args, **kwargs)
    return decorated_function


@mia_bp.route('/')
@login_required
def index():
    """MIA integration landing/info page"""
    from utils.mia_client import get_demo_mia_items
    
    connection = None
    if current_user.is_premium:
        connection = MIAConnection.query.filter_by(user_id=current_user.id).first()
    
    demo_alerts = get_demo_mia_items()
    
    return render_template('mia/index.html',
                         connection=connection,
                         demo_alerts=demo_alerts,
                         is_premium=current_user.is_premium)


@mia_bp.route('/upgrade')
@login_required
def upgrade():
    """Upgrade prompt for non-premium users"""
    return render_template('mia/upgrade.html')


@mia_bp.route('/connect', methods=['GET', 'POST'])
@login_required
@premium_required
def connect():
    """Connect to MIA platform"""
    connection = MIAConnection.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        
        if not api_key:
            flash('Please enter your MIA API key.', 'error')
            return redirect(url_for('mia.connect'))
        
        from utils.mia_client import MIAClient
        
        client = MIAClient(api_key=api_key)
        result = client.validate_connection()
        
        if not connection:
            connection = MIAConnection(user_id=current_user.id)
            db.session.add(connection)
        
        connection.api_key = api_key
        
        if result.get('success'):
            connection.is_active = True
            connection.connected_at = datetime.utcnow()
            connection.sync_status = 'connected'
            flash('Successfully connected to Market Inefficiency Agents!', 'success')
        else:
            connection.is_active = False
            connection.sync_status = 'error'
            flash(f'Connection test pending. You can configure settings now.', 'info')
        
        db.session.commit()
        return redirect(url_for('mia.settings'))
    
    return render_template('mia/connect.html', connection=connection)


@mia_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@premium_required
def settings():
    """MIA integration settings"""
    connection = MIAConnection.query.filter_by(user_id=current_user.id).first()
    
    if not connection:
        flash('Please connect your MIA account first.', 'info')
        return redirect(url_for('mia.connect'))
    
    if request.method == 'POST':
        connection.show_in_feed = 'show_in_feed' in request.form
        connection.alert_frequency = request.form.get('alert_frequency', 'realtime')
        connection.min_confidence = int(request.form.get('min_confidence', 50))
        
        enabled_markets = request.form.getlist('enabled_markets')
        connection.enabled_markets = json.dumps(enabled_markets) if enabled_markets else None
        
        db.session.commit()
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('mia.settings'))
    
    enabled_markets = []
    if connection.enabled_markets:
        try:
            enabled_markets = json.loads(connection.enabled_markets)
        except:
            pass
    
    available_markets = [
        ('crypto', 'Cryptocurrency'),
        ('equities', 'Equities (Stocks)'),
        ('healthcare', 'Healthcare Sector'),
        ('reits', 'Real Estate (REITs)'),
        ('bonds', 'Fixed Income (Bonds)'),
        ('etfs', 'ETFs'),
        ('forex', 'Foreign Exchange'),
        ('commodities', 'Commodities')
    ]
    
    return render_template('mia/settings.html',
                         connection=connection,
                         enabled_markets=enabled_markets,
                         available_markets=available_markets)


@mia_bp.route('/disconnect', methods=['POST'])
@login_required
@premium_required
def disconnect():
    """Disconnect from MIA platform"""
    connection = MIAConnection.query.filter_by(user_id=current_user.id).first()
    
    if connection:
        connection.is_active = False
        connection.api_key = None
        connection.sync_status = 'disconnected'
        db.session.commit()
        flash('Disconnected from Market Inefficiency Agents.', 'info')
    
    return redirect(url_for('mia.index'))


@mia_bp.route('/alerts')
@login_required
@premium_required
def alerts():
    """View recent MIA alerts"""
    from utils.mia_client import fetch_mia_feed_items, get_demo_mia_items
    
    connection = MIAConnection.query.filter_by(user_id=current_user.id).first()
    
    if not connection or not connection.is_active:
        alerts = get_demo_mia_items()
        is_demo = True
    else:
        alerts = fetch_mia_feed_items(current_user, limit=50)
        is_demo = False
        if not alerts:
            alerts = get_demo_mia_items()
            is_demo = True
    
    return render_template('mia/alerts.html',
                         alerts=alerts,
                         is_demo=is_demo,
                         connection=connection)


@mia_bp.route('/api/alerts')
@login_required
@premium_required
def api_alerts():
    """API endpoint for fetching MIA alerts (for AJAX refresh)"""
    from utils.mia_client import fetch_mia_feed_items
    
    limit = request.args.get('limit', 10, type=int)
    alerts = fetch_mia_feed_items(current_user, limit=limit)
    
    return jsonify({
        'success': True,
        'alerts': alerts,
        'count': len(alerts)
    })


@mia_bp.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint for receiving real-time MIA triggers"""
    webhook_secret = request.headers.get('X-MIA-Signature')
    
    try:
        data = request.get_json()
        
        if not data or 'alert' not in data:
            return jsonify({'error': 'Invalid payload'}), 400
        
        alert_data = data['alert']
        
        existing = MIAAlert.query.filter_by(external_id=alert_data.get('id')).first()
        if not existing:
            alert = MIAAlert(
                external_id=alert_data.get('id'),
                title=alert_data.get('title', 'Market Alert'),
                content=alert_data.get('description'),
                severity=alert_data.get('severity', 'info'),
                market=alert_data.get('market'),
                agent_name=alert_data.get('agent'),
                confidence=alert_data.get('confidence', 0),
                alert_type=alert_data.get('type'),
                extra_data=json.dumps(alert_data.get('metadata', {}))
            )
            db.session.add(alert)
            db.session.commit()
            
            logger.info(f'Received MIA alert: {alert.title}')
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f'MIA webhook error: {e}')
        return jsonify({'error': str(e)}), 500
