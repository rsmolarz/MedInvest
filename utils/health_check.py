"""
Health Check System for MedInvest.
Provides endpoints and utilities for monitoring application health.
"""
import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


class HealthChecker:
    """Health check manager for various services."""
    
    @staticmethod
    def check_database() -> Dict:
        """Check database connectivity."""
        try:
            from app import db
            start = time.time()
            db.session.execute(db.text('SELECT 1'))
            duration = (time.time() - start) * 1000
            
            return {
                'healthy': True,
                'latency_ms': round(duration, 2),
                'message': 'Database connection successful'
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'healthy': False,
                'message': str(e)
            }
    
    @staticmethod
    def check_stripe() -> Dict:
        """Check Stripe API connectivity."""
        try:
            from utils.stripe_client import get_stripe
            
            stripe = get_stripe()
            if not stripe:
                return {
                    'healthy': True,
                    'message': 'Stripe not configured (optional)'
                }
            
            start = time.time()
            stripe.Balance.retrieve()
            duration = (time.time() - start) * 1000
            
            return {
                'healthy': True,
                'latency_ms': round(duration, 2),
                'message': 'Stripe API accessible'
            }
        except Exception as e:
            logger.error(f"Stripe health check failed: {e}")
            return {
                'healthy': False,
                'message': str(e)
            }
    
    @staticmethod
    def check_email() -> Dict:
        """Check email service availability."""
        try:
            api_key = os.environ.get('SENDGRID_API_KEY')
            
            if not api_key:
                return {
                    'healthy': True,
                    'message': 'Email service not configured (optional)'
                }
            
            return {
                'healthy': True,
                'message': 'SendGrid API key configured'
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e)
            }
    
    @staticmethod
    def check_disk_space() -> Dict:
        """Check available disk space."""
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            
            free_gb = free / (1024 ** 3)
            usage_percent = (used / total) * 100
            
            return {
                'healthy': usage_percent < 90,
                'free_gb': round(free_gb, 2),
                'usage_percent': round(usage_percent, 1),
                'message': 'Low disk space' if usage_percent >= 90 else 'Disk space OK'
            }
        except Exception as e:
            return {
                'healthy': True,
                'message': f'Could not check: {e}'
            }
    
    @staticmethod
    def check_memory() -> Dict:
        """Check memory usage."""
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = usage.ru_maxrss / 1024
            
            return {
                'healthy': memory_mb < 512,
                'memory_mb': round(memory_mb, 2),
                'message': 'Memory usage OK' if memory_mb < 512 else 'High memory usage'
            }
        except Exception as e:
            return {
                'healthy': True,
                'message': f'Could not check: {e}'
            }
    
    @staticmethod
    def get_app_info() -> Dict:
        """Get application information."""
        return {
            'name': 'MedInvest',
            'version': '2.0.0',
            'environment': os.environ.get('REPL_SLUG', 'development'),
            'python_version': os.popen('python --version').read().strip(),
            'uptime_seconds': int(time.time() - getattr(HealthChecker, '_start_time', time.time()))
        }


HealthChecker._start_time = time.time()


@health_bp.route('/health')
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


@health_bp.route('/health/live')
def liveness_check():
    """Kubernetes-style liveness probe."""
    return jsonify({'status': 'alive'}), 200


@health_bp.route('/health/ready')
def readiness_check():
    """Kubernetes-style readiness probe."""
    db_check = HealthChecker.check_database()
    
    if db_check['healthy']:
        return jsonify({'status': 'ready'}), 200
    else:
        return jsonify({'status': 'not ready', 'reason': db_check['message']}), 503


@health_bp.route('/health/detailed')
def detailed_health():
    """Detailed health check with all services."""
    checks = {
        'database': HealthChecker.check_database(),
        'stripe': HealthChecker.check_stripe(),
        'email': HealthChecker.check_email(),
        'disk': HealthChecker.check_disk_space(),
        'memory': HealthChecker.check_memory(),
    }
    
    all_healthy = all(c.get('healthy', False) for c in checks.values())
    critical_healthy = checks['database'].get('healthy', False)
    
    if all_healthy:
        status = 'healthy'
        status_code = 200
    elif critical_healthy:
        status = 'degraded'
        status_code = 200
    else:
        status = 'unhealthy'
        status_code = 503
    
    return jsonify({
        'status': status,
        'checks': checks,
        'app': HealthChecker.get_app_info(),
        'timestamp': datetime.utcnow().isoformat()
    }), status_code


@health_bp.route('/health/metrics')
def metrics():
    """Prometheus-style metrics endpoint."""
    from models import User, Post, Subscription
    
    try:
        total_users = User.query.count()
        active_subscriptions = Subscription.query.filter_by(status='active').count()
        total_posts = Post.query.count()
    except Exception:
        total_users = 0
        active_subscriptions = 0
        total_posts = 0
    
    metrics_text = f"""# HELP medinvest_users_total Total number of users
# TYPE medinvest_users_total gauge
medinvest_users_total {total_users}

# HELP medinvest_subscriptions_active Active subscriptions
# TYPE medinvest_subscriptions_active gauge
medinvest_subscriptions_active {active_subscriptions}

# HELP medinvest_posts_total Total number of posts
# TYPE medinvest_posts_total gauge
medinvest_posts_total {total_posts}

# HELP medinvest_up Application is up
# TYPE medinvest_up gauge
medinvest_up 1
"""
    
    return metrics_text, 200, {'Content-Type': 'text/plain'}
