"""
Facebook Page Integration for MedInvest
Auto-posts platform content to Facebook Page with links back to the platform
"""
import os
import logging
import requests
from urllib.parse import urljoin


def get_facebook_token():
    """Get fresh Facebook token - prioritize config file over environment"""
    import json
    # Try reading from config file first (bypasses env caching)
    try:
        with open('facebook_config.json', 'r') as f:
            config = json.load(f)
            if config.get('access_token'):
                return config['access_token']
    except:
        pass
    return os.environ.get('FACEBOOK_PAGE_ACCESS_TOKEN')


def get_facebook_page_id():
    """Get fresh Facebook page ID - prioritize config file over environment"""
    import json
    # Try reading from config file first (bypasses env caching)
    try:
        with open('facebook_config.json', 'r') as f:
            config = json.load(f)
            if config.get('page_id'):
                return config['page_id']
    except:
        pass
    return os.environ.get('FACEBOOK_PAGE_ID')


def get_platform_url():
    """Get platform URL"""
    url = os.environ.get('CUSTOM_DOMAIN', 'medmoneyincubator.com')
    if not url.startswith('http'):
        url = f'https://{url}'
    return url


# For backward compatibility - use getter functions for fresh values
PLATFORM_URL = get_platform_url()


def is_facebook_configured():
    """Check if Facebook page integration is configured"""
    return bool(get_facebook_token() and get_facebook_page_id())


def post_to_facebook(message, link=None, image_url=None):
    """
    Post content to Facebook Page
    
    Args:
        message: Text content of the post
        link: Optional link to include (will generate link preview)
        image_url: Optional image URL to attach
    
    Returns:
        dict with 'success' and 'post_id' or 'error'
    """
    if not is_facebook_configured():
        logging.debug("Facebook page integration not configured, skipping post")
        return {'success': False, 'error': 'Facebook not configured'}
    
    try:
        api_url = f"https://graph.facebook.com/v18.0/{get_facebook_page_id()}/feed"
        
        params = {
            'access_token': get_facebook_token(),
            'message': message
        }
        
        if link:
            params['link'] = link
        
        response = requests.post(api_url, data=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            post_id = data.get('id')
            logging.info(f"Successfully posted to Facebook: {post_id}")
            return {'success': True, 'post_id': post_id}
        else:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            logging.error(f"Facebook API error: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        logging.error(f"Facebook post failed: {e}")
        return {'success': False, 'error': str(e)}


def post_with_photo(message, image_url, link=None):
    """
    Post content with a photo to Facebook Page
    
    Args:
        message: Text content of the post
        image_url: URL of the image to post
        link: Optional link to include in message
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    try:
        api_url = f"https://graph.facebook.com/v18.0/{get_facebook_page_id()}/photos"
        
        full_message = message
        if link:
            full_message = f"{message}\n\n🔗 Read more: {link}"
        
        params = {
            'access_token': get_facebook_token(),
            'message': full_message,
            'url': image_url
        }
        
        response = requests.post(api_url, data=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            post_id = data.get('id')
            logging.info(f"Successfully posted photo to Facebook: {post_id}")
            return {'success': True, 'post_id': post_id}
        else:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            logging.error(f"Facebook photo API error: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        logging.error(f"Facebook photo post failed: {e}")
        return {'success': False, 'error': str(e)}


def share_platform_post(post, author_name=None):
    """
    Share a MedInvest post to Facebook Page
    
    Args:
        post: Post model object
        author_name: Display name of the author (None if anonymous)
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    content = post.content[:400] + '...' if len(post.content) > 400 else post.content
    
    if post.is_anonymous:
        author_display = post.anonymous_name or "Anonymous Physician"
    else:
        author_display = author_name or "A MedInvest member"
    
    message = f"💼 New from {author_display} on MedInvest:\n\n{content}"
    
    post_link = f"{PLATFORM_URL}/post/{post.id}"
    
    message += f"\n\n👉 Join the conversation: {post_link}"
    message += "\n\n#MedInvest #PhysicianInvesting #MedicalProfessionals"
    
    return post_to_facebook(message, link=post_link)


def share_article(article, include_excerpt=True):
    """
    Share an Op-MedInvest article to Facebook Page
    
    Args:
        article: OpMedArticle model object
        include_excerpt: Whether to include article excerpt
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    message = f"📰 New Article: {article.title}"
    
    if include_excerpt and article.excerpt:
        excerpt = article.excerpt[:300] + '...' if len(article.excerpt) > 300 else article.excerpt
        message += f"\n\n{excerpt}"
    
    article_link = f"{PLATFORM_URL}/opmed/article/{article.slug}"
    
    message += f"\n\n📖 Read the full article: {article_link}"
    message += "\n\n#OpMedInvest #PhysicianFinance #InvestmentEducation"
    
    if article.cover_image_url:
        return post_with_photo(message, article.cover_image_url, link=article_link)
    else:
        return post_to_facebook(message, link=article_link)


def share_deal(deal):
    """
    Share an investment deal to Facebook Page
    
    Args:
        deal: InvestmentDeal model object
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    message = f"🏠 New Investment Opportunity: {deal.title}"
    
    if deal.deal_type:
        deal_type_display = deal.deal_type.replace('_', ' ').title()
        message += f"\n\n📊 Type: {deal_type_display}"
    
    if deal.target_raise:
        message += f"\n💰 Target: ${deal.target_raise:,.0f}"
    
    deal_link = f"{PLATFORM_URL}/deals/{deal.id}"
    
    message += f"\n\n🔗 View details (MedInvest members only): {deal_link}"
    message += "\n\n#InvestmentDeals #PhysicianInvesting #RealEstate"
    
    return post_to_facebook(message, link=deal_link)


def share_event(event):
    """
    Share an event to Facebook Page
    
    Args:
        event: Event model object
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    message = f"📅 Upcoming Event: {event.title}"
    
    if event.event_date:
        message += f"\n\n🗓️ {event.event_date.strftime('%B %d, %Y at %I:%M %p')}"
    
    if event.description:
        desc = event.description[:200] + '...' if len(event.description) > 200 else event.description
        message += f"\n\n{desc}"
    
    event_link = f"{PLATFORM_URL}/events/{event.id}"
    
    message += f"\n\n🎟️ Register now: {event_link}"
    message += "\n\n#MedInvestEvents #PhysicianEducation"
    
    return post_to_facebook(message, link=event_link)


def share_ama(ama):
    """
    Share an Expert AMA session to Facebook Page
    
    Args:
        ama: ExpertAMA model object
    """
    if not is_facebook_configured():
        return {'success': False, 'error': 'Facebook not configured'}
    
    message = f"🎙️ Expert AMA: {ama.title}"
    
    message += f"\n\n👤 With: {ama.expert_name}"
    if ama.expert_title:
        message += f" - {ama.expert_title}"
    
    if ama.scheduled_for:
        message += f"\n\n📅 {ama.scheduled_for.strftime('%B %d, %Y at %I:%M %p')}"
    
    if ama.description:
        desc = ama.description[:200] + '...' if len(ama.description) > 200 else ama.description
        message += f"\n\n{desc}"
    
    ama_link = f"{PLATFORM_URL}/ama/{ama.id}"
    
    message += f"\n\n🎯 Register & submit questions: {ama_link}"
    message += "\n\n#ExpertAMA #PhysicianFinance #AskTheExpert"
    
    if ama.expert_image_url:
        return post_with_photo(message, ama.expert_image_url, link=ama_link)
    else:
        return post_to_facebook(message, link=ama_link)
