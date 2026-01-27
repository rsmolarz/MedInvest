"""
Cache Service - Redis-based caching with in-memory fallback
Provides a unified caching interface for the MedInvest platform
"""
import os
import json
import logging
import hashlib
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Optional, Callable, Union

logger = logging.getLogger(__name__)

_redis_client = None
_memory_cache = {}
_memory_cache_expiry = {}
_memory_lock = threading.RLock()


def get_redis_client():
    """Get or create Redis client connection"""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    redis_url = os.environ.get('REDIS_URL') or os.environ.get('REDIS_PRIVATE_URL')
    
    if not redis_url:
        logger.info('No Redis URL configured, using in-memory cache')
        return None
    
    try:
        import redis
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        _redis_client.ping()
        logger.info('Redis connection established')
        return _redis_client
    except Exception as e:
        logger.warning(f'Redis connection failed: {e}. Using in-memory cache.')
        _redis_client = None
        return None


class CacheService:
    """Unified caching service with Redis and in-memory fallback"""
    
    DEFAULT_TTL = 300  # 5 minutes
    
    # Standard TTLs for different data types
    TTL_FEED = 300         # 5 minutes - feeds change frequently
    TTL_PROFILE = 900      # 15 minutes - profile data changes less often
    TTL_TRENDING = 3600    # 1 hour - trending content is aggregated
    TTL_NEWS = 1800        # 30 minutes - external news
    TTL_YOUTUBE = 600      # 10 minutes - YouTube content
    TTL_STATS = 300        # 5 minutes - platform statistics
    TTL_SUGGESTIONS = 600  # 10 minutes - people you may know
    
    # Cache key prefixes for different data types
    PREFIX_USER = 'user:'
    PREFIX_POST = 'post:'
    PREFIX_FEED = 'feed:'
    PREFIX_NEWS = 'news:'
    PREFIX_YOUTUBE = 'youtube:'
    PREFIX_DEALS = 'deals:'
    PREFIX_STATS = 'stats:'
    PREFIX_SESSION = 'session:'
    PREFIX_TRENDING = 'trending:'
    PREFIX_PROFILE = 'profile:'
    
    @classmethod
    def _get_client(cls):
        """Get Redis client or None for memory fallback"""
        return get_redis_client()
    
    @classmethod
    def _clean_expired_memory_cache(cls):
        """Remove expired entries from memory cache (must be called with lock held)"""
        global _memory_cache, _memory_cache_expiry
        now = datetime.utcnow()
        expired_keys = [
            k for k, exp in list(_memory_cache_expiry.items()) 
            if exp < now
        ]
        for key in expired_keys:
            _memory_cache.pop(key, None)
            _memory_cache_expiry.pop(key, None)
    
    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get value from cache"""
        client = cls._get_client()
        
        if client:
            try:
                value = client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error(f'Cache get error: {e}')
        else:
            with _memory_lock:
                cls._clean_expired_memory_cache()
                if key in _memory_cache:
                    return _memory_cache[key]
        
        return None
    
    @classmethod
    def set(cls, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with optional TTL"""
        if ttl is None:
            ttl = cls.DEFAULT_TTL
        
        client = cls._get_client()
        
        if client:
            try:
                client.setex(key, ttl, json.dumps(value, default=str))
                return True
            except Exception as e:
                logger.error(f'Cache set error: {e}')
                return False
        else:
            global _memory_cache, _memory_cache_expiry
            with _memory_lock:
                _memory_cache[key] = value
                _memory_cache_expiry[key] = datetime.utcnow() + timedelta(seconds=ttl)
            return True
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete key from cache"""
        client = cls._get_client()
        
        if client:
            try:
                client.delete(key)
                return True
            except Exception as e:
                logger.error(f'Cache delete error: {e}')
                return False
        else:
            global _memory_cache, _memory_cache_expiry
            with _memory_lock:
                _memory_cache.pop(key, None)
                _memory_cache_expiry.pop(key, None)
            return True
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """Delete all keys matching pattern"""
        client = cls._get_client()
        
        if client:
            try:
                keys = list(client.scan_iter(match=pattern))
                if keys:
                    return client.delete(*keys)
            except Exception as e:
                logger.error(f'Cache delete pattern error: {e}')
        else:
            global _memory_cache, _memory_cache_expiry
            import fnmatch
            with _memory_lock:
                keys_to_delete = [
                    k for k in list(_memory_cache.keys()) 
                    if fnmatch.fnmatch(k, pattern)
                ]
                for key in keys_to_delete:
                    _memory_cache.pop(key, None)
                    _memory_cache_expiry.pop(key, None)
                return len(keys_to_delete)
        
        return 0
    
    @classmethod
    def exists(cls, key: str) -> bool:
        """Check if key exists in cache"""
        client = cls._get_client()
        
        if client:
            try:
                return client.exists(key) > 0
            except Exception as e:
                logger.error(f'Cache exists error: {e}')
                return False
        else:
            with _memory_lock:
                cls._clean_expired_memory_cache()
                return key in _memory_cache
    
    @classmethod
    def increment(cls, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter in cache"""
        client = cls._get_client()
        
        if client:
            try:
                return client.incrby(key, amount)
            except Exception as e:
                logger.error(f'Cache increment error: {e}')
                return None
        else:
            global _memory_cache
            with _memory_lock:
                current = _memory_cache.get(key, 0)
                _memory_cache[key] = current + amount
                return _memory_cache[key]
    
    @classmethod
    def get_many(cls, keys: list) -> dict:
        """Get multiple values from cache"""
        client = cls._get_client()
        result = {}
        
        if client:
            try:
                values = client.mget(keys)
                for key, value in zip(keys, values):
                    if value:
                        result[key] = json.loads(value)
            except Exception as e:
                logger.error(f'Cache get_many error: {e}')
        else:
            with _memory_lock:
                cls._clean_expired_memory_cache()
                for key in keys:
                    if key in _memory_cache:
                        result[key] = _memory_cache[key]
        
        return result
    
    @classmethod
    def set_many(cls, mapping: dict, ttl: int = None) -> bool:
        """Set multiple values in cache"""
        if ttl is None:
            ttl = cls.DEFAULT_TTL
        
        client = cls._get_client()
        
        if client:
            try:
                pipe = client.pipeline()
                for key, value in mapping.items():
                    pipe.setex(key, ttl, json.dumps(value, default=str))
                pipe.execute()
                return True
            except Exception as e:
                logger.error(f'Cache set_many error: {e}')
                return False
        else:
            global _memory_cache, _memory_cache_expiry
            with _memory_lock:
                expiry = datetime.utcnow() + timedelta(seconds=ttl)
                for key, value in mapping.items():
                    _memory_cache[key] = value
                    _memory_cache_expiry[key] = expiry
            return True
    
    @classmethod
    def clear_all(cls) -> bool:
        """Clear all cache (use with caution)"""
        client = cls._get_client()
        
        if client:
            try:
                client.flushdb()
                return True
            except Exception as e:
                logger.error(f'Cache clear error: {e}')
                return False
        else:
            global _memory_cache, _memory_cache_expiry
            with _memory_lock:
                _memory_cache.clear()
                _memory_cache_expiry.clear()
            return True
    
    @classmethod
    def get_stats(cls) -> dict:
        """Get cache statistics"""
        client = cls._get_client()
        
        if client:
            try:
                info = client.info()
                return {
                    'backend': 'redis',
                    'connected': True,
                    'used_memory': info.get('used_memory_human', 'N/A'),
                    'keys': client.dbsize(),
                    'hits': info.get('keyspace_hits', 0),
                    'misses': info.get('keyspace_misses', 0)
                }
            except Exception as e:
                return {'backend': 'redis', 'connected': False, 'error': str(e)}
        else:
            with _memory_lock:
                return {
                    'backend': 'memory',
                    'connected': True,
                    'keys': len(_memory_cache),
                    'memory_entries': len(_memory_cache)
                }


def cached(ttl: int = 300, prefix: str = '', key_builder: Callable = None):
    """
    Decorator for caching function results
    
    Args:
        ttl: Time to live in seconds
        prefix: Cache key prefix
        key_builder: Optional function to build cache key from args/kwargs
    
    Usage:
        @cached(ttl=600, prefix='user_profile:')
        def get_user_profile(user_id):
            return db.query(User).get(user_id)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
                raw_key = ':'.join(key_parts)
                cache_key = hashlib.md5(raw_key.encode()).hexdigest()
            
            full_key = f'{prefix}{cache_key}'
            
            cached_value = CacheService.get(full_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheService.set(full_key, result, ttl)
            
            return result
        
        wrapper.cache_clear = lambda: CacheService.delete_pattern(f'{prefix}*')
        return wrapper
    
    return decorator


def cache_result(ttl: int = None, prefix: str = '', cache_type: str = 'default'):
    """
    Enhanced decorator for caching function results with predefined TTLs
    
    Args:
        ttl: Time to live in seconds (overrides cache_type default)
        prefix: Cache key prefix
        cache_type: One of 'feed', 'profile', 'trending', 'news', 'youtube', 'stats', 'suggestions'
    
    Usage:
        @cache_result(cache_type='feed')
        def get_user_feed(user_id): ...
        
        @cache_result(cache_type='trending')
        def get_trending_posts(): ...
        
        @cache_result(cache_type='profile')
        def get_user_profile(user_id): ...
    """
    ttl_map = {
        'default': CacheService.DEFAULT_TTL,
        'feed': CacheService.TTL_FEED,
        'profile': CacheService.TTL_PROFILE,
        'trending': CacheService.TTL_TRENDING,
        'news': CacheService.TTL_NEWS,
        'youtube': CacheService.TTL_YOUTUBE,
        'stats': CacheService.TTL_STATS,
        'suggestions': CacheService.TTL_SUGGESTIONS,
    }
    
    actual_ttl = ttl if ttl is not None else ttl_map.get(cache_type, CacheService.DEFAULT_TTL)
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key_parts = [func.__name__]
            for arg in args:
                if hasattr(arg, 'id'):
                    key_parts.append(f'id:{arg.id}')
                elif not callable(arg):
                    key_parts.append(str(arg))
            key_parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
            raw_key = ':'.join(key_parts)
            cache_key = hashlib.md5(raw_key.encode()).hexdigest()
            
            full_key = f'{prefix}{cache_key}'
            
            cached_value = CacheService.get(full_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheService.set(full_key, result, actual_ttl)
            
            return result
        
        wrapper.cache_clear = lambda: CacheService.delete_pattern(f'{prefix}*')
        wrapper.cache_invalidate = lambda key: CacheService.delete(key)
        return wrapper
    
    return decorator


def cache_user_data(user_id: int, data: dict, ttl: int = 600):
    """Cache user-related data"""
    key = f'{CacheService.PREFIX_USER}{user_id}'
    return CacheService.set(key, data, ttl)


def get_cached_user_data(user_id: int) -> Optional[dict]:
    """Get cached user data"""
    key = f'{CacheService.PREFIX_USER}{user_id}'
    return CacheService.get(key)


def invalidate_user_cache(user_id: int):
    """Invalidate all cache for a specific user"""
    CacheService.delete_pattern(f'{CacheService.PREFIX_USER}{user_id}*')
    CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*user:{user_id}*')


def cache_feed_page(user_id: int, page: int, feed_type: str, data: list, ttl: int = None):
    """Cache a feed page for a user (5 min default)"""
    if ttl is None:
        ttl = CacheService.TTL_FEED
    key = f'{CacheService.PREFIX_FEED}user:{user_id}:type:{feed_type}:page:{page}'
    return CacheService.set(key, data, ttl)


def get_cached_feed_page(user_id: int, page: int, feed_type: str) -> Optional[list]:
    """Get cached feed page"""
    key = f'{CacheService.PREFIX_FEED}user:{user_id}:type:{feed_type}:page:{page}'
    return CacheService.get(key)


def invalidate_feed_cache(user_id: int = None):
    """Invalidate feed cache for a user or all users"""
    if user_id:
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}user:{user_id}*')
    else:
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*')


def cache_news(category: str, articles: list, ttl: int = 900):
    """Cache news articles by category (15 min default)"""
    key = f'{CacheService.PREFIX_NEWS}{category}'
    return CacheService.set(key, articles, ttl)


def get_cached_news(category: str) -> Optional[list]:
    """Get cached news for category"""
    key = f'{CacheService.PREFIX_NEWS}{category}'
    return CacheService.get(key)


def cache_youtube_content(content_type: str, data: Any, ttl: int = 600):
    """Cache YouTube content (shorts, videos, live status)"""
    key = f'{CacheService.PREFIX_YOUTUBE}{content_type}'
    return CacheService.set(key, data, ttl)


def get_cached_youtube_content(content_type: str) -> Optional[Any]:
    """Get cached YouTube content"""
    key = f'{CacheService.PREFIX_YOUTUBE}{content_type}'
    return CacheService.get(key)


def cache_platform_stats(stats: dict, ttl: int = None):
    """Cache platform-wide statistics (5 min default)"""
    if ttl is None:
        ttl = CacheService.TTL_STATS
    key = f'{CacheService.PREFIX_STATS}platform'
    return CacheService.set(key, stats, ttl)


def get_cached_platform_stats() -> Optional[dict]:
    """Get cached platform statistics"""
    key = f'{CacheService.PREFIX_STATS}platform'
    return CacheService.get(key)


def cache_profile(user_id: int, profile_data: dict, ttl: int = None):
    """Cache user profile data (15 min default)"""
    if ttl is None:
        ttl = CacheService.TTL_PROFILE
    key = f'{CacheService.PREFIX_PROFILE}{user_id}'
    return CacheService.set(key, profile_data, ttl)


def get_cached_profile(user_id: int) -> Optional[dict]:
    """Get cached user profile data"""
    key = f'{CacheService.PREFIX_PROFILE}{user_id}'
    return CacheService.get(key)


def invalidate_profile_cache(user_id: int):
    """Invalidate profile cache for a user"""
    CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}{user_id}*')


def cache_trending(data_type: str, data: Any, ttl: int = None):
    """Cache trending content (1 hour default)"""
    if ttl is None:
        ttl = CacheService.TTL_TRENDING
    key = f'{CacheService.PREFIX_TRENDING}{data_type}'
    return CacheService.set(key, data, ttl)


def get_cached_trending(data_type: str) -> Optional[Any]:
    """Get cached trending content"""
    key = f'{CacheService.PREFIX_TRENDING}{data_type}'
    return CacheService.get(key)


def invalidate_trending_cache():
    """Invalidate all trending content cache"""
    CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}*')


# =============================================================================
# SPECIALIZED CACHE DECORATORS
# =============================================================================

def cache_feed(user_id_arg: int = 0, feed_type: str = 'main'):
    """
    Decorator for caching feed data (5 min TTL)
    
    Args:
        user_id_arg: Position of user_id in function args (0 = first arg)
        feed_type: Type of feed ('main', 'following', 'trending', 'deals')
    
    Usage:
        @cache_feed(user_id_arg=0, feed_type='main')
        def get_user_feed(user_id, page=1, per_page=20): ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = args[user_id_arg] if len(args) > user_id_arg else kwargs.get('user_id')
            page = kwargs.get('page', 1)
            per_page = kwargs.get('per_page', 20)
            
            cache_key = f'{CacheService.PREFIX_FEED}{feed_type}:user:{user_id}:page:{page}:per_page:{per_page}'
            
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                logger.debug(f'Cache hit: {cache_key}')
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheService.set(cache_key, result, CacheService.TTL_FEED)
                logger.debug(f'Cache set: {cache_key}')
            
            return result
        
        wrapper.invalidate = lambda user_id: CacheService.delete_pattern(
            f'{CacheService.PREFIX_FEED}{feed_type}:user:{user_id}*'
        )
        wrapper.invalidate_all = lambda: CacheService.delete_pattern(
            f'{CacheService.PREFIX_FEED}{feed_type}:*'
        )
        return wrapper
    
    return decorator


def cache_profile_data(user_id_arg: int = 0):
    """
    Decorator for caching user profile data (15 min TTL)
    
    Args:
        user_id_arg: Position of user_id in function args
    
    Usage:
        @cache_profile_data(user_id_arg=0)
        def get_user_profile(user_id): ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = args[user_id_arg] if len(args) > user_id_arg else kwargs.get('user_id')
            
            cache_key = f'{CacheService.PREFIX_PROFILE}{func.__name__}:{user_id}'
            
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                logger.debug(f'Cache hit: {cache_key}')
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheService.set(cache_key, result, CacheService.TTL_PROFILE)
                logger.debug(f'Cache set: {cache_key}')
            
            return result
        
        wrapper.invalidate = lambda user_id: CacheService.delete_pattern(
            f'{CacheService.PREFIX_PROFILE}{func.__name__}:{user_id}*'
        )
        wrapper.invalidate_all = lambda: CacheService.delete_pattern(
            f'{CacheService.PREFIX_PROFILE}{func.__name__}:*'
        )
        return wrapper
    
    return decorator


def cache_trending_data(data_type: str = 'posts'):
    """
    Decorator for caching trending data (1 hour TTL)
    
    Args:
        data_type: Type of trending data ('posts', 'hashtags', 'users', 'deals')
    
    Usage:
        @cache_trending_data(data_type='posts')
        def get_trending_posts(limit=20): ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limit = kwargs.get('limit', 20)
            timeframe = kwargs.get('timeframe', '24h')
            
            cache_key = f'{CacheService.PREFIX_TRENDING}{data_type}:limit:{limit}:timeframe:{timeframe}'
            
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                logger.debug(f'Cache hit: {cache_key}')
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheService.set(cache_key, result, CacheService.TTL_TRENDING)
                logger.debug(f'Cache set: {cache_key}')
            
            return result
        
        wrapper.invalidate = lambda: CacheService.delete_pattern(
            f'{CacheService.PREFIX_TRENDING}{data_type}:*'
        )
        return wrapper
    
    return decorator


# =============================================================================
# POST UPDATE CACHE INVALIDATION STRATEGY
# =============================================================================

class PostCacheInvalidator:
    """
    Comprehensive cache invalidation for post-related updates.
    Ensures all related caches are properly invalidated when posts change.
    """
    
    @classmethod
    def on_post_created(cls, post_id: int, author_id: int, hashtags: list = None):
        """
        Invalidate caches when a new post is created.
        
        Affected caches:
        - Author's feed caches (they might see their own post)
        - Followers' feed caches (they should see the new post)
        - Trending caches (new post might affect trending)
        - Hashtag caches (if post has hashtags)
        """
        logger.info(f'Invalidating caches for new post {post_id} by user {author_id}')
        
        # Invalidate author's feeds
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*user:{author_id}*')
        
        # Invalidate 'following' feeds for all users (followers will see this)
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}following:*')
        
        # Invalidate 'main' feeds (general feed might show this)
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}main:*')
        
        # Invalidate trending if hashtags used
        if hashtags:
            CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}hashtags:*')
            CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}posts:*')
        
        # Invalidate platform stats
        CacheService.delete(f'{CacheService.PREFIX_STATS}platform')
    
    @classmethod
    def on_post_updated(cls, post_id: int, author_id: int):
        """
        Invalidate caches when a post is edited.
        
        Affected caches:
        - Specific post cache
        - Author's profile (post count might change display)
        - Feeds containing this post
        """
        logger.info(f'Invalidating caches for updated post {post_id}')
        
        # Invalidate specific post cache
        CacheService.delete(f'{CacheService.PREFIX_POST}{post_id}')
        
        # Invalidate author's feeds and profile
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*user:{author_id}*')
        CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}*:{author_id}*')
        
        # Invalidate general feeds that might contain this post
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}main:*')
    
    @classmethod
    def on_post_deleted(cls, post_id: int, author_id: int):
        """
        Invalidate caches when a post is deleted.
        
        Affected caches:
        - All caches affected by post_updated
        - Trending caches (post removal affects rankings)
        - Stats caches
        """
        logger.info(f'Invalidating caches for deleted post {post_id}')
        
        # Delete specific post cache
        CacheService.delete(f'{CacheService.PREFIX_POST}{post_id}')
        
        # Invalidate all feeds (post removal affects many feeds)
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*')
        
        # Invalidate author's profile
        CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}*:{author_id}*')
        
        # Invalidate trending (rankings change)
        CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}*')
        
        # Invalidate platform stats
        CacheService.delete(f'{CacheService.PREFIX_STATS}platform')
    
    @classmethod
    def on_post_liked(cls, post_id: int, post_author_id: int, liker_id: int):
        """
        Invalidate caches when a post is liked.
        
        Affected caches:
        - Specific post cache (like count changed)
        - Trending posts (engagement affects ranking)
        - Liker's activity cache
        """
        logger.debug(f'Invalidating caches for liked post {post_id}')
        
        # Invalidate specific post cache
        CacheService.delete(f'{CacheService.PREFIX_POST}{post_id}')
        
        # Invalidate trending (engagement changed)
        CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}posts:*')
        
        # Invalidate liker's activity
        CacheService.delete_pattern(f'{CacheService.PREFIX_USER}{liker_id}:activity*')
    
    @classmethod
    def on_post_commented(cls, post_id: int, post_author_id: int, commenter_id: int):
        """
        Invalidate caches when a comment is added to a post.
        
        Affected caches:
        - Specific post cache (comment count changed)
        - Trending posts (engagement affects ranking)
        - Commenter's activity cache
        """
        logger.debug(f'Invalidating caches for commented post {post_id}')
        
        # Invalidate specific post cache
        CacheService.delete(f'{CacheService.PREFIX_POST}{post_id}')
        
        # Invalidate trending (engagement changed)
        CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}posts:*')
        
        # Invalidate commenter's activity
        CacheService.delete_pattern(f'{CacheService.PREFIX_USER}{commenter_id}:activity*')
    
    @classmethod
    def on_user_followed(cls, follower_id: int, followed_id: int):
        """
        Invalidate caches when a user follows another.
        
        Affected caches:
        - Follower's 'following' feed (they now see new content)
        - Both users' profile caches (follower counts changed)
        - Suggestions cache for follower
        """
        logger.debug(f'Invalidating caches for follow: {follower_id} -> {followed_id}')
        
        # Invalidate follower's 'following' feed
        CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}following:user:{follower_id}*')
        
        # Invalidate both profiles
        CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}*:{follower_id}*')
        CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}*:{followed_id}*')
        
        # Invalidate suggestions for follower
        CacheService.delete_pattern(f'{CacheService.PREFIX_USER}{follower_id}:suggestions*')
    
    @classmethod
    def on_bulk_operation(cls, operation_type: str = 'full'):
        """
        Invalidate caches for bulk operations.
        
        Args:
            operation_type: 'full' clears everything, 'feeds' clears feed caches only
        """
        logger.info(f'Bulk cache invalidation: {operation_type}')
        
        if operation_type == 'full':
            CacheService.clear_all()
        elif operation_type == 'feeds':
            CacheService.delete_pattern(f'{CacheService.PREFIX_FEED}*')
        elif operation_type == 'trending':
            CacheService.delete_pattern(f'{CacheService.PREFIX_TRENDING}*')
        elif operation_type == 'profiles':
            CacheService.delete_pattern(f'{CacheService.PREFIX_PROFILE}*')


# Convenience instance
post_cache = PostCacheInvalidator()
