"""
Rate Limiting Service - Protect against brute force and abuse
Uses Redis with in-memory fallback for tracking request counts
"""
import os
import time
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_memory_store = {}
_memory_lock = threading.RLock()


class RateLimiter:
    """Rate limiting with Redis backend and memory fallback"""
    
    LOGIN_LIMIT = 5
    LOGIN_WINDOW = 300
    API_LIMIT = 1000
    API_WINDOW = 60
    GENERAL_LIMIT = 100
    GENERAL_WINDOW = 60
    
    @classmethod
    def _get_redis_client(cls):
        """Get Redis client if available"""
        from utils.cache_service import get_redis_client
        return get_redis_client()
    
    @classmethod
    def _get_key(cls, identifier: str, action: str) -> str:
        """Generate rate limit key"""
        return f"rate_limit:{action}:{identifier}"
    
    @classmethod
    def _memory_get(cls, key: str) -> Tuple[int, float]:
        """Get count and expiry from memory store"""
        with _memory_lock:
            if key in _memory_store:
                count, expiry = _memory_store[key]
                if time.time() < expiry:
                    return count, expiry
                else:
                    del _memory_store[key]
            return 0, 0
    
    @classmethod
    def _memory_incr(cls, key: str, window: int) -> int:
        """Increment count in memory store"""
        with _memory_lock:
            now = time.time()
            if key in _memory_store:
                count, expiry = _memory_store[key]
                if now < expiry:
                    count += 1
                    _memory_store[key] = (count, expiry)
                    return count
            
            expiry = now + window
            _memory_store[key] = (1, expiry)
            return 1
    
    @classmethod
    def _memory_reset(cls, key: str):
        """Reset rate limit in memory"""
        with _memory_lock:
            if key in _memory_store:
                del _memory_store[key]
    
    @classmethod
    def check_rate_limit(cls, identifier: str, action: str, limit: int, window: int) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit
        
        Returns:
            (allowed, remaining, reset_time)
        """
        key = cls._get_key(identifier, action)
        client = cls._get_redis_client()
        
        if client:
            try:
                pipe = client.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                results = pipe.execute()
                
                current_count = results[0]
                ttl = results[1]
                
                if ttl == -1:
                    client.expire(key, window)
                    ttl = window
                
                remaining = max(0, limit - current_count)
                reset_time = int(time.time()) + (ttl if ttl > 0 else window)
                
                return current_count <= limit, remaining, reset_time
                
            except Exception as e:
                logger.error(f"Redis rate limit error: {e}")
        
        current_count = cls._memory_incr(key, window)
        remaining = max(0, limit - current_count)
        reset_time = int(time.time()) + window
        
        return current_count <= limit, remaining, reset_time
    
    @classmethod
    def check_login_limit(cls, identifier: str) -> Tuple[bool, int, int]:
        """Check login rate limit (5 attempts per 5 minutes)"""
        return cls.check_rate_limit(identifier, 'login', cls.LOGIN_LIMIT, cls.LOGIN_WINDOW)
    
    @classmethod
    def check_api_limit(cls, identifier: str) -> Tuple[bool, int, int]:
        """Check API rate limit (1000 requests per minute)"""
        return cls.check_rate_limit(identifier, 'api', cls.API_LIMIT, cls.API_WINDOW)
    
    @classmethod
    def check_general_limit(cls, identifier: str) -> Tuple[bool, int, int]:
        """Check general request rate limit (100 requests per minute)"""
        return cls.check_rate_limit(identifier, 'general', cls.GENERAL_LIMIT, cls.GENERAL_WINDOW)
    
    @classmethod
    def reset_login_limit(cls, identifier: str):
        """Reset login rate limit after successful login"""
        key = cls._get_key(identifier, 'login')
        client = cls._get_redis_client()
        
        if client:
            try:
                client.delete(key)
                return
            except Exception as e:
                logger.error(f"Redis reset error: {e}")
        
        cls._memory_reset(key)
    
    @classmethod
    def get_remaining_lockout_time(cls, identifier: str) -> int:
        """Get remaining lockout time in seconds"""
        key = cls._get_key(identifier, 'login')
        client = cls._get_redis_client()
        
        if client:
            try:
                ttl = client.ttl(key)
                if ttl > 0:
                    count = int(client.get(key) or 0)
                    if count >= cls.LOGIN_LIMIT:
                        return ttl
                return 0
            except Exception as e:
                logger.error(f"Redis TTL error: {e}")
        
        with _memory_lock:
            if key in _memory_store:
                count, expiry = _memory_store[key]
                if count >= cls.LOGIN_LIMIT and time.time() < expiry:
                    return int(expiry - time.time())
        
        return 0


def rate_limit(limit: int = 100, window: int = 60, key_func=None):
    """
    Decorator to rate limit a route
    
    Args:
        limit: Maximum requests allowed
        window: Time window in seconds
        key_func: Optional function to generate rate limit key from request
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if key_func:
                identifier = key_func()
            else:
                from flask_login import current_user
                if hasattr(current_user, 'id') and current_user.is_authenticated:
                    identifier = f"user:{current_user.id}"
                else:
                    identifier = request.remote_addr or 'unknown'
            
            allowed, remaining, reset_time = RateLimiter.check_rate_limit(
                identifier, f.__name__, limit, window
            )
            
            g.rate_limit_remaining = remaining
            g.rate_limit_reset = reset_time
            
            if not allowed:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Please try again in {reset_time - int(time.time())} seconds.',
                    'retry_after': reset_time - int(time.time())
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(reset_time)
                response.headers['Retry-After'] = str(reset_time - int(time.time()))
                return response
            
            response = f(*args, **kwargs)
            
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(reset_time)
            
            return response
        return wrapper
    return decorator


def login_rate_limit():
    """Decorator specifically for login endpoints (5 attempts per 5 min)"""
    return rate_limit(
        limit=RateLimiter.LOGIN_LIMIT,
        window=RateLimiter.LOGIN_WINDOW,
        key_func=lambda: request.remote_addr or 'unknown'
    )


def api_rate_limit():
    """Decorator for API endpoints (1000 requests per minute)"""
    return rate_limit(
        limit=RateLimiter.API_LIMIT,
        window=RateLimiter.API_WINDOW
    )
