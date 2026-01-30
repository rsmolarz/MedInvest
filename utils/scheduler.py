"""
Background Scheduler for MedInvest
Handles scheduled tasks like hourly code reviews
"""
import os
import logging
import atexit
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = None


def run_code_review_job():
    """Execute the hourly code review"""
    from app import app
    
    with app.app_context():
        try:
            from utils.code_quality_guardian import CodeQualityGuardian
            logger.info('Starting scheduled code review...')
            guardian = CodeQualityGuardian()
            result = guardian.run_review()
            logger.info(f'Scheduled code review completed: {result}')
        except Exception as e:
            logger.error(f'Scheduled code review failed: {e}')


def init_scheduler(app):
    """Initialize the background scheduler
    
    To prevent multiple scheduler instances in multi-worker environments,
    this only runs when explicitly enabled via SCHEDULER_ENABLED=true
    """
    global _scheduler
    
    if os.environ.get('SCHEDULER_DISABLED'):
        logger.info('Scheduler disabled by environment variable')
        return
    
    if not os.environ.get('SCHEDULER_ENABLED'):
        logger.info('Scheduler not enabled (set SCHEDULER_ENABLED=true to enable)')
        return
    
    if _scheduler is not None:
        logger.info('Scheduler already initialized')
        return
    
    try:
        # Use memory-based job store to avoid ZoneInfo pickle issues with SQLAlchemy job store
        _scheduler = BackgroundScheduler(timezone='UTC')
        
        _scheduler.add_job(
            func=run_code_review_job,
            trigger=CronTrigger(minute=0),
            id='hourly_code_review',
            name='Hourly Code Quality Review',
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        
        _scheduler.start()
        logger.info('Background scheduler started with hourly code review job')
        
        atexit.register(lambda: _scheduler.shutdown())
        
    except Exception as e:
        logger.error(f'Failed to initialize scheduler: {e}')


def get_scheduler_status():
    """Get current scheduler status"""
    global _scheduler
    
    if _scheduler is None:
        return {'running': False, 'jobs': []}
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return {
        'running': _scheduler.running,
        'jobs': jobs
    }
