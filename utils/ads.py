"""
Ad Serving Utilities
"""
import random
from datetime import datetime
from app import db
from models import AdCreative, AdCampaign, AdImpression
from flask_login import current_user


def get_active_ad(format_type, user_id=None):
    """
    Get an active ad creative for a specific format type.
    
    Args:
        format_type: One of 'sidebar', 'medicine_money_show', 'deal_inline', 'feed'
        user_id: Optional user ID for impression tracking
        
    Returns:
        AdCreative object or None
    """
    now = datetime.utcnow()
    
    query = db.session.query(AdCreative).join(AdCampaign).filter(
        AdCreative.is_active == True,
        AdCreative.format == format_type,
        AdCampaign.start_at <= now,
        db.or_(AdCampaign.end_at >= now, AdCampaign.end_at.is_(None))
    )
    
    creatives = query.all()
    
    if not creatives:
        return None
    
    selected = random.choice(creatives)
    
    if user_id:
        try:
            impression = AdImpression(
                creative_id=selected.id,
                user_id=user_id
            )
            db.session.add(impression)
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    return selected


def get_sidebar_ads(user_id=None, limit=2):
    """
    Get sidebar ads (both medicine_money_show and general sidebar).
    
    Returns:
        dict with 'medicine_money_show' and 'sidebar' keys
    """
    ads = {
        'medicine_money_show': get_active_ad('medicine_money_show', user_id),
        'sidebar': get_active_ad('sidebar', user_id)
    }
    return ads


def get_deal_inline_ad(user_id=None):
    """Get an inline ad for deals pages."""
    return get_active_ad('deal_inline', user_id)


def get_feed_ad(user_id=None):
    """Get a feed ad to display between posts."""
    return get_active_ad('feed', user_id)
