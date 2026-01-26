"""Simple scheduler for background jobs without extra dependencies."""
import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleScheduler:
    """Simple interval-based job scheduler."""
    
    def __init__(self):
        self.jobs = []
        self.running = False
        self.thread = None
    
    def add_job(self, func, interval_seconds: int, name: str = None):
        """Add a job to run at the specified interval."""
        self.jobs.append({
            'func': func,
            'interval': interval_seconds,
            'name': name or func.__name__,
            'last_run': None
        })
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            now = datetime.utcnow()
            
            for job in self.jobs:
                if job['last_run'] is None:
                    # Run immediately on first pass
                    self._run_job(job)
                else:
                    elapsed = (now - job['last_run']).total_seconds()
                    if elapsed >= job['interval']:
                        self._run_job(job)
            
            # Sleep for 60 seconds between checks
            time.sleep(60)
    
    def _run_job(self, job):
        """Run a single job."""
        try:
            logger.info(f"Running job: {job['name']}")
            job['func']()
            job['last_run'] = datetime.utcnow()
            logger.info(f"Completed job: {job['name']}")
        except Exception as e:
            logger.error(f"Error running job {job['name']}: {e}")
            job['last_run'] = datetime.utcnow()  # Still update to avoid rapid retries


def send_daily_digest():
    """Send daily email digest to subscribers"""
    try:
        from app import app
        with app.app_context():
            from utils.email_digest import send_digests
            send_digests('daily')
    except Exception as e:
        logger.error(f"Error sending daily digest: {e}")


def send_weekly_digest():
    """Send weekly email digest to subscribers"""
    try:
        from app import app
        with app.app_context():
            from utils.email_digest import send_digests
            send_digests('weekly')
    except Exception as e:
        logger.error(f"Error sending weekly digest: {e}")


def create_default_scheduler():
    """Create scheduler with default ops jobs."""
    from ops_jobs import (
        monitor_verification_sla_and_alert,
        auto_route_verification_queue,
        invite_credit_boosts_by_specialty,
        run_all_ops_jobs
    )
    
    scheduler = SimpleScheduler()
    
    # Run SLA monitoring every 15 minutes
    scheduler.add_job(monitor_verification_sla_and_alert, 900, 'sla_monitor')
    
    # Run auto-routing every 5 minutes
    scheduler.add_job(auto_route_verification_queue, 300, 'auto_route')
    
    # Run invite boosts daily (86400 seconds)
    scheduler.add_job(invite_credit_boosts_by_specialty, 86400, 'invite_boosts')
    
    # Email digests - daily at 8am UTC (every 24 hours)
    scheduler.add_job(send_daily_digest, 86400, 'daily_email_digest')
    
    # Weekly digest every 7 days
    scheduler.add_job(send_weekly_digest, 604800, 'weekly_email_digest')
    
    return scheduler


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    scheduler = create_default_scheduler()
    scheduler.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
