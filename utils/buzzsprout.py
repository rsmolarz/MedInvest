"""
Buzzsprout Podcast Integration
Fetches podcast episodes from Buzzsprout API
"""
import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_buzzsprout_episodes(podcast_id=None, api_token=None, max_results=12):
    """
    Fetch podcast episodes from Buzzsprout API
    
    Args:
        podcast_id: Buzzsprout podcast ID (from URL or settings)
        api_token: Buzzsprout API token
        max_results: Maximum number of episodes to return
    
    Returns:
        list of episode dicts with id, title, description, audio_url, artwork_url, 
        published_at, duration, episode_number
    """
    from models import SiteSettings
    
    if not podcast_id or not api_token:
        settings = SiteSettings.query.first()
        if settings:
            podcast_id = podcast_id or getattr(settings, 'buzzsprout_podcast_id', None)
            api_token = api_token or os.environ.get('BUZZSPROUT_API_TOKEN')
    
    if not podcast_id or not api_token:
        logger.warning('Buzzsprout not configured: missing podcast_id or api_token')
        return []
    
    try:
        response = requests.get(
            f'https://www.buzzsprout.com/api/{podcast_id}/episodes.json',
            headers={
                'Authorization': f'Token token={api_token}',
                'User-Agent': 'MedInvest/1.0'
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        episodes = []
        for ep in data[:max_results]:
            if ep.get('private', False):
                continue
                
            duration_seconds = ep.get('duration', 0)
            duration_formatted = format_duration(duration_seconds)
            
            episodes.append({
                'id': ep.get('id'),
                'title': ep.get('title', ''),
                'description': ep.get('description', ''),
                'summary': ep.get('summary', ''),
                'audio_url': ep.get('audio_url', ''),
                'artwork_url': ep.get('artwork_url', ''),
                'published_at': ep.get('published_at', ''),
                'duration': duration_seconds,
                'duration_formatted': duration_formatted,
                'episode_number': ep.get('episode_number'),
                'season_number': ep.get('season_number'),
                'total_plays': ep.get('total_plays', 0),
                'artist': ep.get('artist', ''),
                'tags': ep.get('tags', '')
            })
        
        return episodes
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error('Buzzsprout API authentication failed - check API token')
        elif e.response.status_code == 404:
            logger.error(f'Buzzsprout podcast not found: {podcast_id}')
        else:
            logger.error(f'Buzzsprout API error: {e}')
        return []
    except Exception as e:
        logger.error(f'Failed to fetch Buzzsprout episodes: {e}')
        return []


def get_buzzsprout_podcast_info(podcast_id=None, api_token=None):
    """
    Get podcast metadata from Buzzsprout
    
    Returns:
        dict with id, title, author, description, artwork_url
    """
    from models import SiteSettings
    
    if not podcast_id or not api_token:
        settings = SiteSettings.query.first()
        if settings:
            podcast_id = podcast_id or getattr(settings, 'buzzsprout_podcast_id', None)
            api_token = api_token or os.environ.get('BUZZSPROUT_API_TOKEN')
    
    if not podcast_id or not api_token:
        return None
    
    try:
        response = requests.get(
            'https://www.buzzsprout.com/api/podcasts.json',
            headers={
                'Authorization': f'Token token={api_token}',
                'User-Agent': 'MedInvest/1.0'
            },
            timeout=10
        )
        response.raise_for_status()
        podcasts = response.json()
        
        for podcast in podcasts:
            if str(podcast.get('id')) == str(podcast_id):
                return {
                    'id': podcast.get('id'),
                    'title': podcast.get('title', ''),
                    'author': podcast.get('author', ''),
                    'description': podcast.get('description', ''),
                    'artwork_url': podcast.get('artwork_url', ''),
                    'language': podcast.get('language', 'en-us'),
                    'timezone': podcast.get('timezone', '')
                }
        
        return None
        
    except Exception as e:
        logger.error(f'Failed to get Buzzsprout podcast info: {e}')
        return None


def is_buzzsprout_configured():
    """Check if Buzzsprout is properly configured"""
    from models import SiteSettings
    
    settings = SiteSettings.query.first()
    if not settings:
        return False
    
    podcast_id = getattr(settings, 'buzzsprout_podcast_id', None)
    api_token = os.environ.get('BUZZSPROUT_API_TOKEN')
    enabled = getattr(settings, 'buzzsprout_enabled', False)
    
    return bool(podcast_id and api_token and enabled)


def format_duration(seconds):
    """Format duration in seconds to human readable string"""
    if not seconds:
        return ''
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    else:
        return f'{minutes}:{secs:02d}'
