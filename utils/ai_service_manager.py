"""
AI Service Manager - Centralized AI provider management with failover and rate limiting

Features:
- Multi-provider support (Gemini, OpenAI, etc.)
- Automatic failover between providers
- Rate limiting (global and per-user)
- Request caching for efficiency
- Usage tracking and cost estimation
- Health monitoring for providers
- API key rotation with multiple keys
- Automatic retry with exponential backoff
- Request/response logging for debugging
- Circuit breaker pattern for failing services
"""

import os
import time
import logging
import hashlib
import json
import random
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def can_execute(self) -> bool:
        """Check if circuit allows execution"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                if self.last_failure_time and \
                   (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
                return False
            else:  # HALF_OPEN
                return self.half_open_calls < self.half_open_max_calls
    
    def record_success(self):
        """Record successful call"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN


@dataclass
class APIKeyRotator:
    """Manages multiple API keys with rotation"""
    keys: List[str] = field(default_factory=list)
    current_index: int = 0
    usage_counts: Dict[int, int] = field(default_factory=dict)
    failed_keys: set = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def add_key(self, key: str):
        """Add a new API key"""
        with self._lock:
            if key and key not in self.keys:
                self.keys.append(key)
                self.usage_counts[len(self.keys) - 1] = 0
    
    def get_key(self) -> Optional[str]:
        """Get next available API key (round-robin)"""
        with self._lock:
            if not self.keys:
                return None
            
            available_indices = [i for i in range(len(self.keys)) if i not in self.failed_keys]
            if not available_indices:
                self.failed_keys.clear()
                available_indices = list(range(len(self.keys)))
            
            self.current_index = available_indices[self.current_index % len(available_indices)]
            key = self.keys[self.current_index]
            self.usage_counts[self.current_index] = self.usage_counts.get(self.current_index, 0) + 1
            self.current_index = (self.current_index + 1) % len(self.keys)
            return key
    
    def mark_failed(self, key: str):
        """Mark a key as temporarily failed"""
        with self._lock:
            try:
                idx = self.keys.index(key)
                self.failed_keys.add(idx)
            except ValueError:
                pass
    
    def mark_recovered(self, key: str):
        """Mark a key as recovered"""
        with self._lock:
            try:
                idx = self.keys.index(key)
                self.failed_keys.discard(idx)
            except ValueError:
                pass


@dataclass 
class RequestLog:
    """Log entry for AI requests"""
    timestamp: datetime
    provider: str
    model: str
    prompt_hash: str
    prompt_preview: str
    response_preview: str
    tokens_used: int
    latency_ms: float
    success: bool
    error: str = ""
    user_id: int = 0


class RequestLogger:
    """Logs AI requests and responses for debugging"""
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.logs: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
    
    def log(
        self, provider: str, model: str, prompt: str, response: str,
        tokens: int, latency_ms: float, success: bool, error: str = "",
        user_id: int = 0
    ):
        """Log a request/response pair"""
        entry = RequestLog(
            timestamp=datetime.now(),
            provider=provider,
            model=model,
            prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
            prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
            response_preview=response[:100] + "..." if len(response) > 100 else response,
            tokens_used=tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
            user_id=user_id
        )
        with self._lock:
            self.logs.append(entry)
    
    def get_recent(self, count: int = 50, user_id: int = 0) -> List[RequestLog]:
        """Get recent log entries"""
        with self._lock:
            logs = list(self.logs)
            if user_id:
                logs = [l for l in logs if l.user_id == user_id]
            return logs[-count:]
    
    def get_errors(self, count: int = 50) -> List[RequestLog]:
        """Get recent error entries"""
        with self._lock:
            return [l for l in list(self.logs) if not l.success][-count:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        with self._lock:
            logs = list(self.logs)
            if not logs:
                return {'total': 0}
            
            success_count = sum(1 for l in logs if l.success)
            return {
                'total': len(logs),
                'success': success_count,
                'failure': len(logs) - success_count,
                'success_rate': round((success_count / len(logs)) * 100, 2),
                'avg_latency_ms': round(sum(l.latency_ms for l in logs) / len(logs), 2),
                'total_tokens': sum(l.tokens_used for l in logs),
                'by_provider': {
                    p: sum(1 for l in logs if l.provider == p)
                    for p in set(l.provider for l in logs)
                }
            }


class UserRateLimiter:
    """Per-user rate limiting"""
    
    def __init__(self, max_requests_per_minute: int = 20, max_tokens_per_minute: int = 50000):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.user_requests: Dict[int, List[float]] = {}
        self.user_tokens: Dict[int, List[tuple]] = {}
        self._lock = threading.Lock()
    
    def _cleanup_user(self, user_id: int, cutoff: float):
        """Clean up expired entries for a user"""
        if user_id in self.user_requests:
            self.user_requests[user_id] = [t for t in self.user_requests[user_id] if t > cutoff]
        if user_id in self.user_tokens:
            self.user_tokens[user_id] = [(t, n) for t, n in self.user_tokens[user_id] if t > cutoff]
    
    def can_proceed(self, user_id: int, token_count: int = 0) -> bool:
        """Check if user can make a request"""
        with self._lock:
            now = time.time()
            cutoff = now - 60
            self._cleanup_user(user_id, cutoff)
            
            requests = self.user_requests.get(user_id, [])
            if len(requests) >= self.max_requests:
                return False
            
            tokens = self.user_tokens.get(user_id, [])
            current_tokens = sum(n for _, n in tokens)
            if current_tokens + token_count > self.max_tokens:
                return False
            
            return True
    
    def record(self, user_id: int, token_count: int = 0):
        """Record a user request"""
        with self._lock:
            now = time.time()
            if user_id not in self.user_requests:
                self.user_requests[user_id] = []
            if user_id not in self.user_tokens:
                self.user_tokens[user_id] = []
            
            self.user_requests[user_id].append(now)
            if token_count > 0:
                self.user_tokens[user_id].append((now, token_count))
    
    def get_user_usage(self, user_id: int) -> Dict[str, int]:
        """Get current usage for a user"""
        with self._lock:
            now = time.time()
            cutoff = now - 60
            self._cleanup_user(user_id, cutoff)
            
            requests = len(self.user_requests.get(user_id, []))
            tokens = sum(n for _, n in self.user_tokens.get(user_id, []))
            
            return {
                'requests_this_minute': requests,
                'tokens_this_minute': tokens,
                'requests_remaining': max(0, self.max_requests - requests),
                'tokens_remaining': max(0, self.max_tokens - tokens)
            }


class AIProvider(Enum):
    """Supported AI providers"""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class RequestPriority(Enum):
    """Request priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ProviderConfig:
    """Configuration for an AI provider"""
    name: AIProvider
    api_key_env: str
    base_url: Optional[str] = None
    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 100000
    cost_per_1k_tokens: float = 0.0
    timeout_seconds: int = 30
    enabled: bool = True
    priority: int = 1
    models: List[str] = field(default_factory=list)
    
    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)
    
    @property
    def is_available(self) -> bool:
        return self.enabled and self.api_key is not None


@dataclass
class UsageStats:
    """Track usage statistics for a provider"""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    requests_this_minute: int = 0
    tokens_this_minute: int = 0
    minute_start: Optional[datetime] = None


@dataclass
class CacheEntry:
    """Cached AI response"""
    response: Any
    created_at: datetime
    ttl_seconds: int
    hits: int = 0


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, max_requests: int, max_tokens: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds
        self.requests = []
        self.tokens = []
        self._lock = threading.Lock()
    
    def _cleanup(self):
        """Remove expired entries"""
        now = time.time()
        cutoff = now - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
        self.tokens = [(t, n) for t, n in self.tokens if t > cutoff]
    
    def can_proceed(self, token_count: int = 0) -> bool:
        """Check if request can proceed"""
        with self._lock:
            self._cleanup()
            
            if len(self.requests) >= self.max_requests:
                return False
            
            current_tokens = sum(n for _, n in self.tokens)
            if current_tokens + token_count > self.max_tokens:
                return False
            
            return True
    
    def record(self, token_count: int = 0):
        """Record a request"""
        with self._lock:
            now = time.time()
            self.requests.append(now)
            if token_count > 0:
                self.tokens.append((now, token_count))
    
    def wait_time(self) -> float:
        """Get seconds to wait before next request"""
        with self._lock:
            self._cleanup()
            if len(self.requests) < self.max_requests:
                return 0
            oldest = min(self.requests)
            return max(0, self.window_seconds - (time.time() - oldest))


class AIServiceManager:
    """Centralized manager for AI services with failover, rate limiting, and circuit breakers
    
    Features:
    - Multi-provider support with automatic failover
    - API key rotation with multiple keys per provider
    - Global and per-user rate limiting
    - Circuit breaker pattern for fault tolerance
    - Request/response logging for debugging
    - Automatic retry with exponential backoff
    - Usage tracking and cost estimation
    """
    
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
    RETRY_MAX_DELAY = 30.0
    
    DEFAULT_PROVIDERS = {
        AIProvider.GEMINI: ProviderConfig(
            name=AIProvider.GEMINI,
            api_key_env="AI_INTEGRATIONS_GEMINI_API_KEY",
            max_requests_per_minute=60,
            max_tokens_per_minute=100000,
            cost_per_1k_tokens=0.00025,
            timeout_seconds=30,
            priority=1,
            models=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
        ),
        AIProvider.OPENAI: ProviderConfig(
            name=AIProvider.OPENAI,
            api_key_env="OPENAI_API_KEY",
            base_url="https://api.openai.com/v1",
            max_requests_per_minute=60,
            max_tokens_per_minute=90000,
            cost_per_1k_tokens=0.002,
            timeout_seconds=30,
            priority=2,
            models=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
        ),
        AIProvider.ANTHROPIC: ProviderConfig(
            name=AIProvider.ANTHROPIC,
            api_key_env="ANTHROPIC_API_KEY",
            base_url="https://api.anthropic.com/v1",
            max_requests_per_minute=50,
            max_tokens_per_minute=80000,
            cost_per_1k_tokens=0.003,
            timeout_seconds=30,
            priority=3,
            models=["claude-3-haiku-20240307", "claude-3-sonnet-20240229"]
        )
    }
    
    def __init__(self, cache_ttl: int = 3600, max_cache_size: int = 1000):
        self.providers: Dict[AIProvider, ProviderConfig] = {}
        self.rate_limiters: Dict[AIProvider, RateLimiter] = {}
        self.usage_stats: Dict[AIProvider, UsageStats] = {}
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self.health_status: Dict[AIProvider, bool] = {}
        self._lock = threading.Lock()
        
        self.circuit_breakers: Dict[AIProvider, CircuitBreaker] = {}
        self.key_rotators: Dict[AIProvider, APIKeyRotator] = {}
        self.user_rate_limiter = UserRateLimiter()
        self.request_logger = RequestLogger()
        self.fallback_enabled = os.environ.get('AI_FALLBACK_ENABLED', 'true').lower() == 'true'
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers with circuit breakers and key rotators"""
        for provider, config in self.DEFAULT_PROVIDERS.items():
            if config.is_available:
                self.providers[provider] = config
                self.rate_limiters[provider] = RateLimiter(
                    config.max_requests_per_minute,
                    config.max_tokens_per_minute
                )
                self.usage_stats[provider] = UsageStats()
                self.health_status[provider] = True
                self.circuit_breakers[provider] = CircuitBreaker()
                
                rotator = APIKeyRotator()
                if config.api_key:
                    rotator.add_key(config.api_key)
                additional_keys = os.environ.get(f"{config.api_key_env}_ADDITIONAL", "")
                for key in additional_keys.split(","):
                    if key.strip():
                        rotator.add_key(key.strip())
                self.key_rotators[provider] = rotator
                
                logger.info(f"Initialized AI provider: {provider.value} with {len(rotator.keys)} key(s)")
    
    def add_api_key(self, provider: AIProvider, key: str):
        """Add an additional API key for rotation"""
        if provider in self.key_rotators:
            self.key_rotators[provider].add_key(key)
            logger.info(f"Added new API key for {provider.value}")
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.RETRY_BASE_DELAY * (2 ** attempt),
            self.RETRY_MAX_DELAY
        )
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of available and healthy providers sorted by priority"""
        available = [
            p for p in self.providers.keys()
            if self.health_status.get(p, False) and self.providers[p].is_available
        ]
        return sorted(available, key=lambda p: self.providers[p].priority)
    
    def get_primary_provider(self) -> Optional[AIProvider]:
        """Get the highest priority available provider"""
        providers = self.get_available_providers()
        return providers[0] if providers else None
    
    def _generate_cache_key(self, prompt: str, model: str, **kwargs) -> str:
        """Generate cache key for request"""
        key_data = f"{prompt}:{model}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached response if valid"""
        with self._lock:
            entry = self.cache.get(cache_key)
            if entry:
                if datetime.now() - entry.created_at < timedelta(seconds=entry.ttl_seconds):
                    entry.hits += 1
                    return entry.response
                else:
                    del self.cache[cache_key]
        return None
    
    def _set_cached(self, cache_key: str, response: Any, ttl: Optional[int] = None):
        """Cache a response"""
        with self._lock:
            if len(self.cache) >= self.max_cache_size:
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k].created_at)
                del self.cache[oldest_key]
            
            self.cache[cache_key] = CacheEntry(
                response=response,
                created_at=datetime.now(),
                ttl_seconds=ttl or self.cache_ttl
            )
    
    def _update_stats(self, provider: AIProvider, tokens: int, latency_ms: float, success: bool):
        """Update usage statistics"""
        stats = self.usage_stats.get(provider)
        if not stats:
            return
        
        stats.total_requests += 1
        stats.total_tokens += tokens
        stats.last_request_time = datetime.now()
        
        if success:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1
        
        n = stats.total_requests
        stats.avg_latency_ms = ((stats.avg_latency_ms * (n - 1)) + latency_ms) / n
        
        config = self.providers.get(provider)
        if config:
            stats.total_cost += (tokens / 1000) * config.cost_per_1k_tokens
    
    def _mark_unhealthy(self, provider: AIProvider, error: str):
        """Mark a provider as unhealthy"""
        self.health_status[provider] = False
        logger.warning(f"Provider {provider.value} marked unhealthy: {error}")
    
    def _mark_healthy(self, provider: AIProvider):
        """Mark a provider as healthy"""
        self.health_status[provider] = True
    
    async def generate_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[AIProvider] = None,
        use_cache: bool = True,
        priority: RequestPriority = RequestPriority.NORMAL,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        fallback: bool = True,
        user_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate AI response asynchronously with automatic failover
        
        Args:
            prompt: The input prompt
            model: Specific model to use (optional)
            provider: Specific provider to use (optional)
            use_cache: Whether to use cache
            priority: Request priority
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            fallback: Whether to fallback to other providers on failure
            user_id: Optional user ID for per-user rate limiting
            
        Returns:
            Dict with response, provider used, tokens, latency, etc.
        """
        import httpx
        import asyncio
        
        if user_id and not self.user_rate_limiter.can_proceed(user_id, max_tokens):
            user_usage = self.user_rate_limiter.get_user_usage(user_id)
            return {
                'error': 'User rate limit exceeded',
                'response': None,
                'provider': None,
                'user_usage': user_usage
            }
        
        cache_key = self._generate_cache_key(prompt, model or "", **kwargs)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return {
                    'response': cached,
                    'provider': 'cache',
                    'tokens': 0,
                    'latency_ms': 0,
                    'from_cache': True
                }
        
        providers_to_try = []
        if provider:
            providers_to_try = [provider]
        else:
            providers_to_try = self.get_available_providers()
        
        if not providers_to_try:
            return {
                'error': 'No AI providers available',
                'response': None,
                'provider': None
            }
        
        last_error = None
        for prov in providers_to_try:
            config = self.providers.get(prov)
            if not config:
                continue
            
            circuit_breaker = self.circuit_breakers.get(prov)
            if circuit_breaker and not circuit_breaker.can_execute():
                logger.info(f"Circuit breaker open for {prov.value}, skipping")
                continue
            
            limiter = self.rate_limiters.get(prov)
            if limiter and not limiter.can_proceed(max_tokens):
                wait_time = limiter.wait_time()
                if wait_time > 0 and priority.value < RequestPriority.HIGH.value:
                    logger.info(f"Rate limited on {prov.value}, trying next provider")
                    continue
            
            for attempt in range(self.MAX_RETRIES):
                try:
                    start_time = time.time()
                    response = await self._call_provider(prov, prompt, model, max_tokens, temperature, **kwargs)
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if limiter:
                        limiter.record(response.get('tokens_used', max_tokens))
                    
                    if user_id:
                        self.user_rate_limiter.record(user_id, response.get('tokens_used', max_tokens))
                    
                    self._update_stats(prov, response.get('tokens_used', 0), latency_ms, True)
                    self._mark_healthy(prov)
                    
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    
                    response_text = response.get('text', '')
                    tokens_used = response.get('tokens_used', 0)
                    
                    self.request_logger.log(
                        provider=prov.value,
                        model=response.get('model', model or ''),
                        prompt=prompt,
                        response=response_text,
                        tokens=tokens_used,
                        latency_ms=latency_ms,
                        success=True,
                        user_id=user_id or 0
                    )
                    
                    if use_cache:
                        self._set_cached(cache_key, response_text)
                    
                    return {
                        'response': response_text,
                        'provider': prov.value,
                        'model': response.get('model', model),
                        'tokens': tokens_used,
                        'latency_ms': latency_ms,
                        'from_cache': False,
                        'attempts': attempt + 1
                    }
                    
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed for {prov.value}: {e}")
                    
                    if attempt < self.MAX_RETRIES - 1:
                        delay = self._calculate_retry_delay(attempt)
                        logger.info(f"Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    else:
                        self._update_stats(prov, 0, 0, False)
                        if circuit_breaker:
                            circuit_breaker.record_failure()
                        
                        self.request_logger.log(
                            provider=prov.value,
                            model=model or '',
                            prompt=prompt,
                            response='',
                            tokens=0,
                            latency_ms=0,
                            success=False,
                            error=last_error or '',
                            user_id=user_id or 0
                        )
                        
                        if not self.fallback_enabled or not fallback:
                            break
        
        return {
            'error': last_error or 'All providers failed',
            'response': None,
            'provider': None
        }
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[AIProvider] = None,
        use_cache: bool = True,
        priority: RequestPriority = RequestPriority.NORMAL,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        fallback: bool = True,
        user_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Synchronous wrapper for generate_async"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.generate_async(
                prompt, model, provider, use_cache, priority,
                max_tokens, temperature, fallback, user_id, **kwargs
            )
        )
    
    async def _call_provider(
        self,
        provider: AIProvider,
        prompt: str,
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Call a specific provider's API"""
        import httpx
        
        config = self.providers[provider]
        
        if provider == AIProvider.GEMINI:
            return await self._call_gemini(config, prompt, model, max_tokens, temperature, **kwargs)
        elif provider == AIProvider.OPENAI:
            return await self._call_openai(config, prompt, model, max_tokens, temperature, **kwargs)
        elif provider == AIProvider.ANTHROPIC:
            return await self._call_anthropic(config, prompt, model, max_tokens, temperature, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def _call_gemini(
        self, config: ProviderConfig, prompt: str, model: Optional[str],
        max_tokens: int, temperature: float, **kwargs
    ) -> Dict[str, Any]:
        """Call Gemini API"""
        import google.generativeai as genai  # type: ignore
        
        genai.configure(api_key=config.api_key)
        model_name = model or config.models[0] if config.models else "gemini-1.5-flash"
        
        gen_model = genai.GenerativeModel(model_name)
        response = gen_model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature
            }
        )
        
        return {
            'text': response.text,
            'model': model_name,
            'tokens_used': len(prompt.split()) + len(response.text.split())
        }
    
    async def _call_openai(
        self, config: ProviderConfig, prompt: str, model: Optional[str],
        max_tokens: int, temperature: float, **kwargs
    ) -> Dict[str, Any]:
        """Call OpenAI API"""
        import httpx
        
        model_name = model or config.models[0] if config.models else "gpt-4o-mini"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=config.timeout_seconds
            )
            response.raise_for_status()
            data = response.json()
        
        return {
            'text': data['choices'][0]['message']['content'],
            'model': model_name,
            'tokens_used': data.get('usage', {}).get('total_tokens', 0)
        }
    
    async def _call_anthropic(
        self, config: ProviderConfig, prompt: str, model: Optional[str],
        max_tokens: int, temperature: float, **kwargs
    ) -> Dict[str, Any]:
        """Call Anthropic API"""
        import httpx
        
        model_name = model or config.models[0] if config.models else "claude-3-haiku-20240307"
        api_key = config.api_key or ""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.base_url}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=config.timeout_seconds
            )
            response.raise_for_status()
            data = response.json()
        
        return {
            'text': data['content'][0]['text'],
            'model': model_name,
            'tokens_used': data.get('usage', {}).get('input_tokens', 0) + data.get('usage', {}).get('output_tokens', 0)
        }
    
    def get_usage_report(self) -> Dict[str, Any]:
        """Get usage statistics for all providers"""
        report = {
            'providers': {},
            'totals': {
                'requests': 0,
                'tokens': 0,
                'cost': 0.0,
                'success_rate': 0.0
            },
            'cache': {
                'size': len(self.cache),
                'total_hits': sum(e.hits for e in self.cache.values())
            }
        }
        
        total_success = 0
        total_requests = 0
        
        for provider, stats in self.usage_stats.items():
            report['providers'][provider.value] = {
                'total_requests': stats.total_requests,
                'successful_requests': stats.successful_requests,
                'failed_requests': stats.failed_requests,
                'total_tokens': stats.total_tokens,
                'total_cost': round(stats.total_cost, 4),
                'avg_latency_ms': round(stats.avg_latency_ms, 2),
                'last_request': stats.last_request_time.isoformat() if stats.last_request_time else None,
                'healthy': self.health_status.get(provider, False)
            }
            
            report['totals']['requests'] += stats.total_requests
            report['totals']['tokens'] += stats.total_tokens
            report['totals']['cost'] += stats.total_cost
            total_success += stats.successful_requests
            total_requests += stats.total_requests
        
        if total_requests > 0:
            report['totals']['success_rate'] = round((total_success / total_requests) * 100, 2)
        
        report['totals']['cost'] = round(report['totals']['cost'], 4)
        
        return report
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all providers"""
        results = {}
        for provider in self.providers.keys():
            config = self.providers[provider]
            results[provider.value] = {
                'configured': True,
                'api_key_present': config.api_key is not None,
                'enabled': config.enabled,
                'healthy': self.health_status.get(provider, False),
                'rate_limit_status': 'ok' if self.rate_limiters[provider].can_proceed() else 'limited'
            }
        return results
    
    def clear_cache(self):
        """Clear all cached responses"""
        with self._lock:
            self.cache.clear()
    
    def reset_health_status(self):
        """Reset all providers to healthy status and circuit breakers"""
        for provider in self.providers.keys():
            self.health_status[provider] = True
            if provider in self.circuit_breakers:
                cb = self.circuit_breakers[provider]
                cb.state = CircuitState.CLOSED
                cb.failure_count = 0
    
    def get_request_logs(self, count: int = 50, user_id: int = 0) -> List[Dict]:
        """Get recent request logs"""
        logs = self.request_logger.get_recent(count, user_id)
        return [
            {
                'timestamp': log.timestamp.isoformat(),
                'provider': log.provider,
                'model': log.model,
                'prompt_preview': log.prompt_preview,
                'response_preview': log.response_preview,
                'tokens': log.tokens_used,
                'latency_ms': log.latency_ms,
                'success': log.success,
                'error': log.error,
                'user_id': log.user_id
            }
            for log in logs
        ]
    
    def get_error_logs(self, count: int = 50) -> List[Dict]:
        """Get recent error logs"""
        logs = self.request_logger.get_errors(count)
        return [
            {
                'timestamp': log.timestamp.isoformat(),
                'provider': log.provider,
                'model': log.model,
                'prompt_hash': log.prompt_hash,
                'error': log.error,
                'user_id': log.user_id
            }
            for log in logs
        ]
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get request logging statistics"""
        return self.request_logger.get_stats()
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for all providers"""
        status = {}
        for provider, cb in self.circuit_breakers.items():
            status[provider.value] = {
                'state': cb.state.value,
                'failure_count': cb.failure_count,
                'last_failure': cb.last_failure_time.isoformat() if cb.last_failure_time else None,
                'can_execute': cb.can_execute()
            }
        return status
    
    def get_user_usage(self, user_id: int) -> Dict[str, int]:
        """Get current rate limit usage for a user"""
        return self.user_rate_limiter.get_user_usage(user_id)
    
    def get_key_rotator_status(self) -> Dict[str, Any]:
        """Get API key rotator status for all providers"""
        status = {}
        for provider, rotator in self.key_rotators.items():
            status[provider.value] = {
                'total_keys': len(rotator.keys),
                'failed_keys': len(rotator.failed_keys),
                'available_keys': len(rotator.keys) - len(rotator.failed_keys),
                'usage_counts': dict(rotator.usage_counts)
            }
        return status


ai_service = AIServiceManager()
