"""
Email Digest Service - Send daily/weekly digest emails
"""
from datetime import datetime, timedelta
import logging
from app import db
from models import User, Post, InvestmentDeal, ExpertAMA, Event, NotificationPreference

logger = logging.getLogger(__name__)


def get_digest_recipients(frequency):
    """Get users who have opted into digest emails at given frequency"""
    users = db.session.query(User).join(
        NotificationPreference,
        NotificationPreference.user_id == User.id,
        isouter=True
    ).filter(
        User.account_active == True,
        db.or_(
            NotificationPreference.email_digest == frequency,
            db.and_(NotificationPreference.id == None, frequency == 'weekly')
        )
    ).all()
    
    return users


def generate_digest_content(frequency='weekly'):
    """Generate digest content for the given frequency"""
    now = datetime.utcnow()
    
    if frequency == 'daily':
        since = now - timedelta(days=1)
    else:
        since = now - timedelta(days=7)
    
    # Trending posts
    trending_posts = Post.query.filter(
        Post.created_at >= since
    ).order_by(Post.like_count.desc()).limit(5).all()
    
    # New deals
    new_deals = InvestmentDeal.query.filter(
        InvestmentDeal.created_at >= since,
        InvestmentDeal.status == 'active'
    ).order_by(InvestmentDeal.created_at.desc()).limit(3).all()
    
    # Upcoming AMAs
    upcoming_amas = ExpertAMA.query.filter(
        ExpertAMA.scheduled_date >= now,
        ExpertAMA.status == 'scheduled'
    ).order_by(ExpertAMA.scheduled_date.asc()).limit(3).all()
    
    # Upcoming Events
    upcoming_events = Event.query.filter(
        Event.start_date >= now,
        Event.is_published == True
    ).order_by(Event.start_date.asc()).limit(3).all()
    
    return {
        'frequency': frequency,
        'trending_posts': trending_posts,
        'new_deals': new_deals,
        'upcoming_amas': upcoming_amas,
        'upcoming_events': upcoming_events,
        'generated_at': now
    }


def send_digest_email(user, content, base_url='https://medinvest.com'):
    """Send digest email to a user"""
    from mailer import send_email
    
    subject = f"Your {'Daily' if content['frequency'] == 'daily' else 'Weekly'} MedInvest Digest"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #2563eb;">
            <h1 style="color: #2563eb; margin: 0;">MedInvest</h1>
            <p style="color: #6b7280; margin-top: 5px;">Your {'Daily' if content['frequency'] == 'daily' else 'Weekly'} Digest</p>
        </div>
        
        <p style="margin-top: 20px;">Hi {user.first_name},</p>
        <p>Here's what's happening in the MedInvest community:</p>
    """
    
    # Trending posts
    if content['trending_posts']:
        html_body += """
        <div style="margin: 20px 0; padding: 15px; background: #f8fafc; border-radius: 8px;">
            <h3 style="color: #1f2937; margin-top: 0;">Trending Posts</h3>
        """
        for post in content['trending_posts']:
            preview = post.content[:100] + '...' if len(post.content) > 100 else post.content
            html_body += f"""
            <div style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                <strong>{post.author.full_name}</strong>
                <p style="margin: 5px 0; color: #4b5563;">{preview}</p>
                <small style="color: #9ca3af;">{post.like_count} likes</small>
            </div>
            """
        html_body += "</div>"
    
    # New deals
    if content['new_deals']:
        html_body += """
        <div style="margin: 20px 0; padding: 15px; background: #f0fdf4; border-radius: 8px;">
            <h3 style="color: #166534; margin-top: 0;">New Investment Opportunities</h3>
        """
        for deal in content['new_deals']:
            html_body += f"""
            <div style="padding: 10px 0; border-bottom: 1px solid #dcfce7;">
                <strong>{deal.title}</strong>
                <p style="margin: 5px 0; color: #4b5563;">Min: ${deal.minimum_investment:,.0f} | Returns: {deal.projected_return}</p>
            </div>
            """
        html_body += "</div>"
    
    # Upcoming AMAs
    if content['upcoming_amas']:
        html_body += """
        <div style="margin: 20px 0; padding: 15px; background: #fef3c7; border-radius: 8px;">
            <h3 style="color: #92400e; margin-top: 0;">Upcoming Expert Sessions</h3>
        """
        for ama in content['upcoming_amas']:
            html_body += f"""
            <div style="padding: 10px 0; border-bottom: 1px solid #fde68a;">
                <strong>{ama.title}</strong>
                <p style="margin: 5px 0; color: #4b5563;">with {ama.expert_name} | {ama.scheduled_date.strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>
            """
        html_body += "</div>"
    
    # Upcoming Events
    if content['upcoming_events']:
        html_body += """
        <div style="margin: 20px 0; padding: 15px; background: #eff6ff; border-radius: 8px;">
            <h3 style="color: #1e40af; margin-top: 0;">Upcoming Events</h3>
        """
        for event in content['upcoming_events']:
            html_body += f"""
            <div style="padding: 10px 0; border-bottom: 1px solid #bfdbfe;">
                <strong>{event.title}</strong>
                <p style="margin: 5px 0; color: #4b5563;">{event.start_date.strftime('%B %d, %Y')} | {event.location or 'Online'}</p>
            </div>
            """
        html_body += "</div>"
    
    html_body += f"""
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center;">
            <a href="{base_url}/feed" style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 8px;">Visit MedInvest</a>
        </div>
        
        <p style="margin-top: 30px; color: #9ca3af; font-size: 12px; text-align: center;">
            You're receiving this because you subscribed to {content['frequency']} digests.<br>
            <a href="{base_url}/notifications/preferences" style="color: #2563eb;">Manage preferences</a>
        </p>
    </body>
    </html>
    """
    
    try:
        send_email(
            to_email=user.email,
            subject=subject,
            html_content=html_body
        )
        logger.info(f"Sent {content['frequency']} digest to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send digest to {user.email}: {e}")
        return False


def send_digests(frequency='weekly'):
    """Send digest emails to all subscribed users"""
    recipients = get_digest_recipients(frequency)
    content = generate_digest_content(frequency)
    
    sent_count = 0
    for user in recipients:
        if send_digest_email(user, content):
            sent_count += 1
    
    logger.info(f"Sent {sent_count} {frequency} digests")
    return sent_count
