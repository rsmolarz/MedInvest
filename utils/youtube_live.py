"""
YouTube Live Integration - Check and embed live streams from YouTube channel
Uses Replit YouTube connection for authentication
"""
import os
import requests
import logging
from datetime import datetime, timedelta
from functools import lru_cache

logger = logging.getLogger(__name__)

_connection_settings = None
_settings_expires = None


def get_youtube_access_token():
    """Get access token from Replit YouTube connection"""
    global _connection_settings, _settings_expires
    
    if _connection_settings and _settings_expires and datetime.utcnow() < _settings_expires:
        return _connection_settings.get('settings', {}).get('access_token')
    
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    repl_identity = os.environ.get('REPL_IDENTITY')
    web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
    
    if repl_identity:
        x_replit_token = f'repl {repl_identity}'
    elif web_repl_renewal:
        x_replit_token = f'depl {web_repl_renewal}'
    else:
        logger.warning('No Replit identity token available for YouTube connection')
        return None
    
    if not hostname:
        logger.warning('REPLIT_CONNECTORS_HOSTNAME not set')
        return None
    
    try:
        response = requests.get(
            f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=youtube',
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        items = data.get('items', [])
        if not items:
            logger.warning('No YouTube connection found')
            return None
        
        _connection_settings = items[0]
        settings = _connection_settings.get('settings', {})
        
        expires_at = settings.get('expires_at')
        if expires_at:
            _settings_expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            _settings_expires = datetime.utcnow() + timedelta(minutes=30)
        
        access_token = settings.get('access_token')
        if not access_token:
            oauth = settings.get('oauth', {})
            credentials = oauth.get('credentials', {})
            access_token = credentials.get('access_token')
        
        return access_token
        
    except Exception as e:
        logger.error(f'Failed to get YouTube access token: {e}')
        return None


def get_channel_live_stream(channel_id=None):
    """
    Check if a YouTube channel is currently live and return stream info
    
    Args:
        channel_id: YouTube channel ID. If None, uses configured channel.
    
    Returns:
        dict with live stream info or None if not live
        {
            'video_id': str,
            'title': str,
            'description': str,
            'thumbnail': str,
            'viewer_count': int,
            'embed_url': str
        }
    """
    from models import SiteSettings
    
    if not channel_id:
        settings = SiteSettings.query.first()
        if settings:
            channel_id = settings.youtube_channel_id
    
    if not channel_id:
        return None
    
    access_token = get_youtube_access_token()
    if not access_token:
        return None
    
    try:
        response = requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params={
                'part': 'snippet',
                'channelId': channel_id,
                'eventType': 'live',
                'type': 'video',
                'maxResults': 1
            },
            headers={
                'Authorization': f'Bearer {access_token}'
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        items = data.get('items', [])
        if not items:
            return None
        
        item = items[0]
        video_id = item['id']['videoId']
        snippet = item['snippet']
        
        video_response = requests.get(
            'https://www.googleapis.com/youtube/v3/videos',
            params={
                'part': 'liveStreamingDetails,snippet',
                'id': video_id
            },
            headers={
                'Authorization': f'Bearer {access_token}'
            },
            timeout=10
        )
        video_response.raise_for_status()
        video_data = video_response.json()
        
        viewer_count = 0
        if video_data.get('items'):
            live_details = video_data['items'][0].get('liveStreamingDetails', {})
            viewer_count = int(live_details.get('concurrentViewers', 0))
        
        return {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'viewer_count': viewer_count,
            'embed_url': f'https://www.youtube.com/embed/{video_id}?autoplay=1'
        }
        
    except Exception as e:
        logger.error(f'Failed to check YouTube live status: {e}')
        return None


def get_channel_info(channel_id):
    """Get basic channel information"""
    access_token = get_youtube_access_token()
    if not access_token:
        return None
    
    try:
        response = requests.get(
            'https://www.googleapis.com/youtube/v3/channels',
            params={
                'part': 'snippet,statistics',
                'id': channel_id
            },
            headers={
                'Authorization': f'Bearer {access_token}'
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        items = data.get('items', [])
        if not items:
            return None
        
        item = items[0]
        snippet = item.get('snippet', {})
        stats = item.get('statistics', {})
        
        return {
            'id': channel_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
            'subscriber_count': int(stats.get('subscriberCount', 0)),
            'video_count': int(stats.get('videoCount', 0))
        }
        
    except Exception as e:
        logger.error(f'Failed to get YouTube channel info: {e}')
        return None


def is_youtube_connected():
    """Check if YouTube connection is available"""
    token = get_youtube_access_token()
    return token is not None
