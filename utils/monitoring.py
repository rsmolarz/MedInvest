"""
Monitoring & Observability - Request logging, error tracking, metrics
"""
import os
import time
import logging
import threading
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any, Callable
from flask import request, g, has_request_context

logger = logging.getLogger(__name__)

_metrics_store = {
    'request_count': 0,
    'error_count': 0,
    'response_times': [],
    'slow_queries': [],
    'endpoint_stats': {}
}
_metrics_lock = threading.Lock()

SLOW_QUERY_THRESHOLD_MS = 500
SLOW_REQUEST_THRESHOLD_MS = 1000


class RequestLogger:
    """Request/response logging middleware"""
    
    @staticmethod
    def before_request():
        """Called before each request"""
        g.request_start_time = time.time()
        g.request_id = f"{int(time.time() * 1000)}-{id(request)}"
    
    @staticmethod
    def after_request(response):
        """Called after each request"""
        if not hasattr(g, 'request_start_time'):
            return response
        
        from utils.security import mask_pii
        
        duration_ms = (time.time() - g.request_start_time) * 1000
        
        user_id = None
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                user_id = current_user.id
        except:
            pass
        
        log_data = {
            'request_id': getattr(g, 'request_id', 'unknown'),
            'timestamp': datetime.utcnow().isoformat(),
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'duration_ms': round(duration_ms, 2),
            'user_id': user_id,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:100]
        }
        
        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(f"SLOW_REQUEST: {mask_pii(str(log_data))}")
        else:
            logger.debug(f"REQUEST: {mask_pii(str(log_data))}")
        
        with _metrics_lock:
            _metrics_store['request_count'] += 1
            _metrics_store['response_times'].append(duration_ms)
            if len(_metrics_store['response_times']) > 1000:
                _metrics_store['response_times'] = _metrics_store['response_times'][-1000:]
            
            endpoint = request.endpoint or 'unknown'
            if endpoint not in _metrics_store['endpoint_stats']:
                _metrics_store['endpoint_stats'][endpoint] = {
                    'count': 0,
                    'total_time': 0,
                    'errors': 0
                }
            _metrics_store['endpoint_stats'][endpoint]['count'] += 1
            _metrics_store['endpoint_stats'][endpoint]['total_time'] += duration_ms
            
            if response.status_code >= 400:
                _metrics_store['error_count'] += 1
                _metrics_store['endpoint_stats'][endpoint]['errors'] += 1
        
        response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
        response.headers['X-Response-Time'] = f"{round(duration_ms, 2)}ms"
        
        return response
    
    @staticmethod
    def teardown_request(exception=None):
        """Called at end of request, even on error"""
        if exception:
            logger.error(f"Request error: {exception}")
            with _metrics_lock:
                _metrics_store['error_count'] += 1


class QueryProfiler:
    """Database query profiling and slow query detection"""
    
    _active = False
    _queries = []
    
    @classmethod
    def enable(cls):
        """Enable query profiling"""
        cls._active = True
        cls._queries = []
    
    @classmethod
    def disable(cls):
        """Disable query profiling"""
        cls._active = False
    
    @classmethod
    def log_query(cls, statement: str, parameters: Any, duration_ms: float):
        """Log a database query"""
        if not cls._active:
            return
        
        query_info = {
            'statement': str(statement)[:500],
            'duration_ms': duration_ms,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        cls._queries.append(query_info)
        
        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(f"SLOW_QUERY ({duration_ms:.2f}ms): {statement[:200]}")
            with _metrics_lock:
                _metrics_store['slow_queries'].append(query_info)
                if len(_metrics_store['slow_queries']) > 100:
                    _metrics_store['slow_queries'] = _metrics_store['slow_queries'][-100:]
    
    @classmethod
    def get_queries(cls):
        """Get all logged queries"""
        return cls._queries.copy()
    
    @classmethod
    def clear(cls):
        """Clear logged queries"""
        cls._queries = []


def track_time(name: str = None):
    """Decorator to track execution time of a function"""
    def decorator(f: Callable):
        func_name = name or f.__name__
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
                    logger.warning(f"SLOW_FUNCTION: {func_name} took {duration_ms:.2f}ms")
        return wrapper
    return decorator


def get_metrics() -> Dict[str, Any]:
    """Get current application metrics"""
    with _metrics_lock:
        response_times = _metrics_store['response_times']
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        p50 = sorted(response_times)[len(response_times) // 2] if response_times else 0
        p95_idx = int(len(response_times) * 0.95)
        p95 = sorted(response_times)[p95_idx] if response_times and p95_idx < len(response_times) else 0
        p99_idx = int(len(response_times) * 0.99)
        p99 = sorted(response_times)[p99_idx] if response_times and p99_idx < len(response_times) else 0
        
        return {
            'request_count': _metrics_store['request_count'],
            'error_count': _metrics_store['error_count'],
            'error_rate': (_metrics_store['error_count'] / _metrics_store['request_count'] * 100) if _metrics_store['request_count'] > 0 else 0,
            'avg_response_time_ms': round(avg_response_time, 2),
            'p50_response_time_ms': round(p50, 2),
            'p95_response_time_ms': round(p95, 2),
            'p99_response_time_ms': round(p99, 2),
            'slow_query_count': len(_metrics_store['slow_queries']),
            'endpoint_stats': dict(_metrics_store['endpoint_stats'])
        }


def reset_metrics():
    """Reset all metrics (typically called at start of monitoring period)"""
    with _metrics_lock:
        _metrics_store['request_count'] = 0
        _metrics_store['error_count'] = 0
        _metrics_store['response_times'] = []
        _metrics_store['slow_queries'] = []
        _metrics_store['endpoint_stats'] = {}


def init_sentry():
    """Initialize Sentry error tracking if configured"""
    sentry_dsn = os.environ.get('SENTRY_DSN')
    
    if not sentry_dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration()
            ],
            traces_sample_rate=0.1,
            environment=os.environ.get('REPLIT_DEPLOYMENT', 'development'),
            send_default_pii=False
        )
        
        logger.info("Sentry error tracking initialized")
        return True
        
    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def capture_exception(exception: Exception, context: Dict[str, Any] = None):
    """Capture an exception for error tracking"""
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            
            if has_request_context():
                scope.set_extra('path', request.path)
                scope.set_extra('method', request.method)
            
            sentry_sdk.capture_exception(exception)
            
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to capture exception: {e}")
    
    logger.exception(f"Exception captured: {exception}")


def send_alert(title: str, message: str, severity: str = 'warning'):
    """Send an alert for critical errors (webhook or email)"""
    alert_webhook = os.environ.get('ALERT_WEBHOOK_URL')
    
    if alert_webhook:
        try:
            import requests
            
            payload = {
                'title': title,
                'message': message,
                'severity': severity,
                'timestamp': datetime.utcnow().isoformat(),
                'environment': os.environ.get('REPLIT_DEPLOYMENT', 'development')
            }
            
            requests.post(alert_webhook, json=payload, timeout=5)
            logger.info(f"Alert sent: {title}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    else:
        logger.warning(f"ALERT ({severity}): {title} - {message}")


def setup_monitoring(app):
    """Setup monitoring for Flask app"""
    app.before_request(RequestLogger.before_request)
    app.after_request(RequestLogger.after_request)
    app.teardown_request(RequestLogger.teardown_request)
    
    init_sentry()
    
    @app.route('/health')
    def health_check():
        return 'OK', 200
    
    @app.route('/metrics')
    def metrics_endpoint():
        from flask_login import current_user
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return {'error': 'Unauthorized'}, 401
        return get_metrics()
    
    logger.info("Monitoring initialized")
