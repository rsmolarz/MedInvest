"""
Background Jobs - Scheduled tasks for feed algorithm
Run these periodically to keep scores fresh

Usage:
    # Run score update every 15 minutes
    python jobs.py update_scores
    
    # Run engagement snapshot every hour
    python jobs.py snapshot_engagement
    
    # Run interest decay daily
    python jobs.py decay_interests
    
    # Run all jobs (for testing)
    python jobs.py run_all
"""
import sys
import math
from datetime import datetime, timedelta
from app import create_app, db
from models import (
    Post, PostScore, User, UserInterest, EngagementSnapshot,
    PostVote, Comment, Bookmark, PostHashtag, Hashtag
)


app = create_app()


# =============================================================================
# SCORE UPDATE JOB (Run every 15 minutes)
# =============================================================================

def update_post_scores():
    """
    Update pre-calculated scores for all recent posts
    This is the main job that powers the algorithmic feed
    """
    with app.app_context():
        print(f"[{datetime.utcnow()}] Starting score update job...")
        
        # Configuration
        HALF_LIFE_HOURS = 48
        
        # Get posts from last 7 days
        time_cutoff = datetime.utcnow() - timedelta(days=7)
        posts = Post.query.filter(Post.created_at >= time_cutoff).all()
        
        updated = 0
        created = 0
        
        for post in posts:
            # Calculate engagement score
            engagement = (
                post.upvotes * 1.0 +
                post.comment_count * 3.0 +
                getattr(post, 'share_count', 0) * 4.0 +
                post.view_count * 0.01
            )
            
            # Add bookmark count if available
            bookmark_count = Bookmark.query.filter_by(post_id=post.id).count()
            engagement += bookmark_count * 5.0
            
            # Calculate quality multiplier
            content = post.content or ''
            quality = 1.0
            
            if len(content) > 500:
                quality += 0.3
            elif len(content) > 200:
                quality += 0.2
            
            if post.media_count > 0:
                quality += 0.1
            
            if '#' in content:
                quality += 0.1
            
            if post.upvotes > 0 and post.comment_count / post.upvotes > 0.3:
                quality += 0.3
            
            quality = min(quality, 2.0)
            
            # Calculate author trust (if not anonymous)
            author_trust = 1.0
            if not post.is_anonymous:
                author = post.author
                if author.is_verified:
                    author_trust *= 1.5
                if author.is_premium:
                    author_trust *= 1.2
                if author.level >= 20:
                    author_trust *= 1.5
                elif author.level >= 10:
                    author_trust *= 1.3
                author_trust = min(author_trust, 3.0)
            
            # Calculate time decay
            age_hours = (datetime.utcnow() - post.created_at).total_seconds() / 3600
            decay_constant = math.log(2) / HALF_LIFE_HOURS
            decay = max(math.exp(-decay_constant * age_hours), 0.05)
            
            # Final score
            score = engagement * quality * author_trust * decay
            
            # Calculate engagement velocity (engagement gained in last hour)
            velocity = 0
            last_snapshot = EngagementSnapshot.query.filter_by(post_id=post.id)\
                .order_by(EngagementSnapshot.snapshot_hour.desc()).first()
            
            if last_snapshot:
                hours_diff = (datetime.utcnow() - last_snapshot.snapshot_hour).total_seconds() / 3600
                if hours_diff > 0:
                    engagement_diff = (
                        (post.upvotes - last_snapshot.upvotes) +
                        (post.comment_count - last_snapshot.comments) * 3
                    )
                    velocity = engagement_diff / hours_diff
            
            # Update or create score record
            post_score = PostScore.query.filter_by(post_id=post.id).first()
            
            if post_score:
                post_score.score = score
                post_score.engagement_score = engagement
                post_score.quality_score = quality
                post_score.decay_score = decay
                post_score.engagement_velocity = velocity
                post_score.updated_at = datetime.utcnow()
                updated += 1
            else:
                post_score = PostScore(
                    post_id=post.id,
                    score=score,
                    engagement_score=engagement,
                    quality_score=quality,
                    decay_score=decay,
                    engagement_velocity=velocity
                )
                db.session.add(post_score)
                created += 1
        
        db.session.commit()
        print(f"[{datetime.utcnow()}] Score update complete. Updated: {updated}, Created: {created}")
        
        return {'updated': updated, 'created': created}


# =============================================================================
# ENGAGEMENT SNAPSHOT JOB (Run every hour)
# =============================================================================

def snapshot_engagement():
    """
    Take hourly snapshots of post engagement for velocity calculation
    Used to determine trending posts (posts gaining engagement quickly)
    """
    with app.app_context():
        print(f"[{datetime.utcnow()}] Starting engagement snapshot job...")
        
        # Round to current hour
        now = datetime.utcnow()
        snapshot_hour = now.replace(minute=0, second=0, microsecond=0)
        
        # Get posts from last 48 hours (active posts)
        time_cutoff = now - timedelta(hours=48)
        posts = Post.query.filter(Post.created_at >= time_cutoff).all()
        
        created = 0
        
        for post in posts:
            # Check if snapshot already exists for this hour
            existing = EngagementSnapshot.query.filter_by(
                post_id=post.id,
                snapshot_hour=snapshot_hour
            ).first()
            
            if not existing:
                bookmark_count = Bookmark.query.filter_by(post_id=post.id).count()
                
                snapshot = EngagementSnapshot(
                    post_id=post.id,
                    snapshot_hour=snapshot_hour,
                    upvotes=post.upvotes,
                    comments=post.comment_count,
                    bookmarks=bookmark_count,
                    views=post.view_count
                )
                db.session.add(snapshot)
                created += 1
        
        # Clean up old snapshots (older than 7 days)
        cleanup_cutoff = now - timedelta(days=7)
        deleted = EngagementSnapshot.query.filter(
            EngagementSnapshot.snapshot_hour < cleanup_cutoff
        ).delete()
        
        db.session.commit()
        print(f"[{datetime.utcnow()}] Snapshot complete. Created: {created}, Cleaned up: {deleted}")
        
        return {'created': created, 'deleted': deleted}


# =============================================================================
# USER INTEREST TRACKING JOB (Run after user interactions)
# =============================================================================

def update_user_interest(user_id, interest_type, reference_id, action='view'):
    """
    Update user interest score based on interaction
    Called after user likes, comments, or views content
    
    Args:
        user_id: User who interacted
        interest_type: 'hashtag', 'room', 'specialty', 'author'
        reference_id: ID or name of the interest
        action: 'view', 'like', 'comment', 'bookmark'
    """
    with app.app_context():
        interest = UserInterest.query.filter_by(
            user_id=user_id,
            interest_type=interest_type,
            reference_id=str(reference_id)
        ).first()
        
        if not interest:
            interest = UserInterest(
                user_id=user_id,
                interest_type=interest_type,
                reference_id=str(reference_id)
            )
            db.session.add(interest)
        
        # Update counts based on action
        if action == 'view':
            interest.view_count += 1
            interest.affinity += 0.1
        elif action == 'like':
            interest.like_count += 1
            interest.affinity += 1.0
        elif action == 'comment':
            interest.comment_count += 1
            interest.affinity += 2.0
        elif action == 'bookmark':
            interest.affinity += 3.0
        
        interest.updated_at = datetime.utcnow()
        db.session.commit()


def track_post_interaction(user_id, post_id, action='view'):
    """
    Track a user's interaction with a post
    Updates interests for hashtags, room, and author
    """
    with app.app_context():
        post = Post.query.get(post_id)
        if not post:
            return
        
        # Track author interest (if not anonymous)
        if not post.is_anonymous:
            update_user_interest(user_id, 'author', post.user_id, action)
            
            # Track author's specialty
            if post.author.specialty:
                update_user_interest(user_id, 'specialty', post.author.specialty, action)
        
        # Track room interest
        if post.room_id:
            update_user_interest(user_id, 'room', post.room_id, action)
        
        # Track hashtag interests
        hashtag_links = PostHashtag.query.filter_by(post_id=post_id).all()
        for link in hashtag_links:
            hashtag = Hashtag.query.get(link.hashtag_id)
            if hashtag:
                update_user_interest(user_id, 'hashtag', hashtag.name, action)


# =============================================================================
# INTEREST DECAY JOB (Run daily)
# =============================================================================

def decay_interests():
    """
    Apply decay to user interests so recent interactions matter more
    Run daily to prevent stale interests from dominating
    """
    with app.app_context():
        print(f"[{datetime.utcnow()}] Starting interest decay job...")
        
        # Decay factor (0.95 = 5% decay per day)
        DECAY_FACTOR = 0.95
        
        # Apply decay to all interests
        interests = UserInterest.query.all()
        
        for interest in interests:
            interest.affinity *= DECAY_FACTOR
            
            # Remove interests that have decayed below threshold
            if interest.affinity < 0.1:
                db.session.delete(interest)
        
        db.session.commit()
        print(f"[{datetime.utcnow()}] Interest decay complete. Processed: {len(interests)}")
        
        return {'processed': len(interests)}


# =============================================================================
# TRENDING HASHTAG UPDATE (Run every hour)
# =============================================================================

def update_trending_hashtags():
    """
    Update hashtag trending scores based on recent usage
    Resets daily/weekly counters
    """
    with app.app_context():
        print(f"[{datetime.utcnow()}] Updating trending hashtags...")
        
        now = datetime.utcnow()
        
        # Count posts per hashtag in last 24 hours
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)
        
        hashtags = Hashtag.query.all()
        
        for hashtag in hashtags:
            # Count posts today
            today_count = PostHashtag.query.join(Post).filter(
                PostHashtag.hashtag_id == hashtag.id,
                Post.created_at >= day_ago
            ).count()
            
            # Count posts this week
            week_count = PostHashtag.query.join(Post).filter(
                PostHashtag.hashtag_id == hashtag.id,
                Post.created_at >= week_ago
            ).count()
            
            hashtag.posts_today = today_count
            hashtag.posts_this_week = week_count
        
        db.session.commit()
        print(f"[{datetime.utcnow()}] Hashtag trending update complete.")
        
        return {'hashtags_updated': len(hashtags)}


# =============================================================================
# CLEANUP JOBS
# =============================================================================

def cleanup_old_scores():
    """
    Remove scores for deleted or old posts
    Run weekly
    """
    with app.app_context():
        print(f"[{datetime.utcnow()}] Cleaning up old scores...")
        
        # Remove scores for posts older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        deleted = db.session.query(PostScore).join(Post).filter(
            Post.created_at < cutoff
        ).delete(synchronize_session=False)
        
        db.session.commit()
        print(f"[{datetime.utcnow()}] Cleanup complete. Deleted: {deleted}")
        
        return {'deleted': deleted}


# =============================================================================
# SCHEDULER SETUP (Using APScheduler or similar)
# =============================================================================

def setup_scheduler():
    """
    Set up background job scheduler
    Uses APScheduler if available, otherwise provides cron-compatible functions
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        
        # Update scores every 15 minutes
        scheduler.add_job(
            update_post_scores,
            IntervalTrigger(minutes=15),
            id='update_scores',
            replace_existing=True
        )
        
        # Snapshot engagement every hour
        scheduler.add_job(
            snapshot_engagement,
            IntervalTrigger(hours=1),
            id='snapshot_engagement',
            replace_existing=True
        )
        
        # Update trending hashtags every hour
        scheduler.add_job(
            update_trending_hashtags,
            IntervalTrigger(hours=1),
            id='update_trending',
            replace_existing=True
        )
        
        # Decay interests daily at 3 AM
        scheduler.add_job(
            decay_interests,
            CronTrigger(hour=3),
            id='decay_interests',
            replace_existing=True
        )
        
        # Cleanup weekly on Sunday at 4 AM
        scheduler.add_job(
            cleanup_old_scores,
            CronTrigger(day_of_week='sun', hour=4),
            id='cleanup_scores',
            replace_existing=True
        )
        
        scheduler.start()
        print("Background scheduler started with all jobs.")
        return scheduler
        
    except ImportError:
        print("APScheduler not installed. Use cron or manual job execution.")
        print("Install with: pip install apscheduler")
        return None


# =============================================================================
# CLI INTERFACE
# =============================================================================

def run_all_jobs():
    """Run all jobs once (for testing or initialization)"""
    print("Running all background jobs...")
    
    print("\n1. Updating post scores...")
    update_post_scores()
    
    print("\n2. Taking engagement snapshots...")
    snapshot_engagement()
    
    print("\n3. Updating trending hashtags...")
    update_trending_hashtags()
    
    print("\n4. Decaying interests...")
    decay_interests()
    
    print("\nAll jobs complete!")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python jobs.py <command>")
        print("\nCommands:")
        print("  update_scores      - Update post scores (run every 15 min)")
        print("  snapshot_engagement - Take engagement snapshot (run hourly)")
        print("  update_trending    - Update trending hashtags (run hourly)")
        print("  decay_interests    - Decay user interests (run daily)")
        print("  cleanup            - Clean old data (run weekly)")
        print("  run_all            - Run all jobs once")
        print("  start_scheduler    - Start background scheduler")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'update_scores':
        update_post_scores()
    elif command == 'snapshot_engagement':
        snapshot_engagement()
    elif command == 'update_trending':
        update_trending_hashtags()
    elif command == 'decay_interests':
        decay_interests()
    elif command == 'cleanup':
        cleanup_old_scores()
    elif command == 'run_all':
        run_all_jobs()
    elif command == 'start_scheduler':
        scheduler = setup_scheduler()
        if scheduler:
            print("Scheduler running. Press Ctrl+C to exit.")
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                scheduler.shutdown()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
