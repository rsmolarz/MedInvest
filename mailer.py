"""Email sending abstraction supporting SendGrid and Postmark.

Uses Replit's SendGrid connection for credentials management.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

# Cache for SendGrid credentials (short-lived)
_sendgrid_cache = {'api_key': None, 'from_email': None, 'expires': 0}


def get_email_provider():
    """Get the configured email provider."""
    return os.environ.get('EMAIL_PROVIDER', 'sendgrid').lower()


def _get_sendgrid_credentials():
    """Get SendGrid credentials from Replit connector.
    
    Returns tuple of (api_key, from_email) or (None, None) if not configured.
    """
    import time
    global _sendgrid_cache
    
    # Check cache (valid for 5 minutes)
    if _sendgrid_cache['api_key'] and time.time() < _sendgrid_cache['expires']:
        return _sendgrid_cache['api_key'], _sendgrid_cache['from_email']
    
    # Try Replit connector first
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    if hostname:
        # Build token for authentication
        repl_identity = os.environ.get('REPL_IDENTITY')
        web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
        
        x_replit_token = None
        if repl_identity:
            x_replit_token = f'repl {repl_identity}'
        elif web_repl_renewal:
            x_replit_token = f'depl {web_repl_renewal}'
        
        if x_replit_token:
            try:
                response = requests.get(
                    f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=sendgrid',
                    headers={
                        'Accept': 'application/json',
                        'X_REPLIT_TOKEN': x_replit_token
                    },
                    timeout=5
                )
                
                if response.ok:
                    data = response.json()
                    items = data.get('items', [])
                    if items:
                        settings = items[0].get('settings', {})
                        api_key = settings.get('api_key')
                        from_email = settings.get('from_email', 'noreply@medmoneyincubator.com')
                        
                        if api_key:
                            # Cache for 5 minutes
                            _sendgrid_cache = {
                                'api_key': api_key,
                                'from_email': from_email,
                                'expires': time.time() + 300
                            }
                            logger.info("SendGrid credentials loaded from Replit connector")
                            return api_key, from_email
            except Exception as e:
                logger.error(f"Failed to get SendGrid credentials from Replit connector: {e}")
    else:
        logger.warning("No REPLIT_CONNECTORS_HOSTNAME set - cannot use Replit connector")
    
    # Fallback to environment variables
    api_key = os.environ.get('SENDGRID_API_KEY')
    from_email = os.environ.get('SENDGRID_FROM', 'noreply@medmoneyincubator.com')
    
    if api_key:
        logger.info("Using SendGrid credentials from environment variables")
        return api_key, from_email
    
    logger.error("No SendGrid credentials available from connector or environment")
    return None, None


def send_email(to_email: str, subject: str, html_content: str, text_content: str = None):
    """Send an email using the configured provider.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML body
        text_content: Plain text body (optional)
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    provider = get_email_provider()
    
    if provider == 'sendgrid':
        return _send_sendgrid(to_email, subject, html_content, text_content)
    elif provider == 'postmark':
        return _send_postmark(to_email, subject, html_content, text_content)
    else:
        logger.warning(f"Unknown email provider: {provider}")
        return False


def _send_sendgrid(to_email: str, subject: str, html_content: str, text_content: str = None):
    """Send email via SendGrid using Replit connector credentials."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        logger.info(f"Attempting to send email to {to_email}")
        api_key, from_email = _get_sendgrid_credentials()
        
        if not api_key:
            logger.error("SendGrid not configured - check Replit connector or SENDGRID_API_KEY env var")
            logger.error(f"REPLIT_CONNECTORS_HOSTNAME: {bool(os.environ.get('REPLIT_CONNECTORS_HOSTNAME'))}")
            logger.error(f"REPL_IDENTITY: {bool(os.environ.get('REPL_IDENTITY'))}")
            logger.error(f"WEB_REPL_RENEWAL: {bool(os.environ.get('WEB_REPL_RENEWAL'))}")
            return False
        
        logger.info(f"SendGrid credentials loaded, from_email: {from_email}")
        
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        if text_content:
            message.plain_text_content = text_content
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        logger.info(f"SendGrid email sent to {to_email}, status: {response.status_code}")
        return response.status_code in (200, 201, 202)
        
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False


def _send_postmark(to_email: str, subject: str, html_content: str, text_content: str = None):
    """Send email via Postmark."""
    try:
        import requests
        
        token = os.environ.get('POSTMARK_SERVER_TOKEN')
        from_email = os.environ.get('POSTMARK_FROM', 'noreply@medinvest.com')
        
        if not token:
            logger.warning("POSTMARK_SERVER_TOKEN not set, email not sent")
            return False
        
        payload = {
            'From': from_email,
            'To': to_email,
            'Subject': subject,
            'HtmlBody': html_content
        }
        
        if text_content:
            payload['TextBody'] = text_content
        
        response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': token
            },
            json=payload
        )
        
        logger.info(f"Postmark email sent to {to_email}, status: {response.status_code}")
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Postmark error: {e}")
        return False


def send_ops_alert(subject: str, html_content: str):
    """Send alert to ops admins."""
    admin_emails = os.environ.get('OPS_ADMIN_EMAILS', '').split(',')
    admin_emails = [e.strip() for e in admin_emails if e.strip()]
    
    if not admin_emails:
        logger.warning("OPS_ADMIN_EMAILS not set, alert not sent")
        return False
    
    success = True
    for email in admin_emails:
        if not send_email(email, subject, html_content):
            success = False
    
    return success


def send_verification_sla_alert(metric: str, value_hours: float, threshold_hours: float):
    """Send verification SLA breach alert."""
    subject = f"[MedInvest Alert] Verification SLA Breach - {metric}"
    html_content = f"""
    <h2>Verification SLA Alert</h2>
    <p>The verification queue SLA has been breached:</p>
    <ul>
        <li><strong>Metric:</strong> {metric}</li>
        <li><strong>Current Value:</strong> {value_hours:.1f} hours</li>
        <li><strong>Threshold:</strong> {threshold_hours:.1f} hours</li>
    </ul>
    <p>Please review the verification queue immediately.</p>
    <p><a href="/admin/verifications">View Verification Queue</a></p>
    """
    return send_ops_alert(subject, html_content)


def send_weekly_digest(to_email: str, user_name: str, stats: dict):
    """Send weekly activity digest to user."""
    subject = "Your Weekly MedInvest Digest"
    html_content = f"""
    <h2>Hi {user_name},</h2>
    <p>Here's your weekly activity summary:</p>
    <ul>
        <li>New posts in your feed: {stats.get('new_posts', 0)}</li>
        <li>New deals this week: {stats.get('new_deals', 0)}</li>
        <li>Upcoming AMAs: {stats.get('upcoming_amas', 0)}</li>
    </ul>
    <p><a href="/">Visit MedInvest</a></p>
    """
    return send_email(to_email, subject, html_content)
