"""
Achievements Service - Award achievements based on user activity
"""
from datetime import datetime
import logging
from app import db
from models import Achievement, UserAchievement, User, Post, Follow

logger = logging.getLogger(__name__)

ACHIEVEMENT_DEFINITIONS = [
    {'code': 'first_post', 'name': 'First Steps', 'description': 'Create your first post', 'icon': '📝', 'category': 'content', 'points': 10, 'tier': 'bronze', 'requirement_type': 'count', 'requirement_value': 1, 'requirement_field': 'posts'},
    {'code': 'post_10', 'name': 'Regular Contributor', 'description': 'Create 10 posts', 'icon': '📰', 'category': 'content', 'points': 25, 'tier': 'silver', 'requirement_type': 'count', 'requirement_value': 10, 'requirement_field': 'posts'},
    {'code': 'post_50', 'name': 'Content Creator', 'description': 'Create 50 posts', 'icon': '🎯', 'category': 'content', 'points': 100, 'tier': 'gold', 'requirement_type': 'count', 'requirement_value': 50, 'requirement_field': 'posts'},
    {'code': 'first_follower', 'name': 'Building Connections', 'description': 'Get your first follower', 'icon': '👤', 'category': 'community', 'points': 10, 'tier': 'bronze', 'requirement_type': 'count', 'requirement_value': 1, 'requirement_field': 'followers'},
    {'code': 'followers_10', 'name': 'Rising Star', 'description': 'Get 10 followers', 'icon': '⭐', 'category': 'community', 'points': 25, 'tier': 'silver', 'requirement_type': 'count', 'requirement_value': 10, 'requirement_field': 'followers'},
    {'code': 'followers_50', 'name': 'Influencer', 'description': 'Get 50 followers', 'icon': '🌟', 'category': 'community', 'points': 100, 'tier': 'gold', 'requirement_type': 'count', 'requirement_value': 50, 'requirement_field': 'followers'},
    {'code': 'verified', 'name': 'Verified Physician', 'description': 'Complete verification', 'icon': '✓', 'category': 'engagement', 'points': 50, 'tier': 'silver', 'requirement_type': 'action', 'requirement_value': 1, 'requirement_field': 'verified'},
    {'code': 'premium', 'name': 'Premium Member', 'description': 'Subscribe to premium', 'icon': '👑', 'category': 'engagement', 'points': 50, 'tier': 'gold', 'requirement_type': 'action', 'requirement_value': 1, 'requirement_field': 'premium'},
    {'code': 'first_deal', 'name': 'Deal Hunter', 'description': 'Express interest in your first deal', 'icon': '🤝', 'category': 'investing', 'points': 20, 'tier': 'bronze', 'requirement_type': 'count', 'requirement_value': 1, 'requirement_field': 'deals'},
    {'code': 'deal_5', 'name': 'Active Investor', 'description': 'Express interest in 5 deals', 'icon': '💼', 'category': 'investing', 'points': 50, 'tier': 'silver', 'requirement_type': 'count', 'requirement_value': 5, 'requirement_field': 'deals'},
    {'code': 'first_course', 'name': 'Lifelong Learner', 'description': 'Enroll in your first course', 'icon': '📚', 'category': 'learning', 'points': 15, 'tier': 'bronze', 'requirement_type': 'count', 'requirement_value': 1, 'requirement_field': 'courses'},
    {'code': 'streak_7', 'name': 'Week Warrior', 'description': 'Login 7 days in a row', 'icon': '🔥', 'category': 'engagement', 'points': 25, 'tier': 'silver', 'requirement_type': 'count', 'requirement_value': 7, 'requirement_field': 'streak'},
    {'code': 'streak_30', 'name': 'Monthly Streak', 'description': 'Login 30 days in a row', 'icon': '💪', 'category': 'engagement', 'points': 100, 'tier': 'gold', 'requirement_type': 'count', 'requirement_value': 30, 'requirement_field': 'streak'},
]


def seed_achievements():
    """Seed achievement definitions into database"""
    for ach_def in ACHIEVEMENT_DEFINITIONS:
        existing = Achievement.query.filter_by(code=ach_def['code']).first()
        if not existing:
            ach = Achievement(**ach_def)
            db.session.add(ach)
    db.session.commit()


def award_achievement(user_id, achievement_code):
    """Award an achievement to a user if they don't have it"""
    try:
        achievement = Achievement.query.filter_by(code=achievement_code, is_active=True).first()
        if not achievement:
            return None
        
        existing = UserAchievement.query.filter_by(
            user_id=user_id,
            achievement_id=achievement.id
        ).first()
        
        if existing:
            return None
        
        user_ach = UserAchievement(
            user_id=user_id,
            achievement_id=achievement.id
        )
        db.session.add(user_ach)
        
        user = User.query.get(user_id)
        if user:
            user.add_points(achievement.points)
        
        db.session.commit()
        
        logger.info(f"Awarded achievement {achievement_code} to user {user_id}")
        return user_ach
        
    except Exception as e:
        logger.error(f"Error awarding achievement: {e}")
        db.session.rollback()
        return None


def check_and_award_achievements(user_id):
    """Check all achievements and award any newly earned ones"""
    from models import DealInterest, CourseEnrollment
    
    user = User.query.get(user_id)
    if not user:
        return []
    
    awarded = []
    
    post_count = Post.query.filter_by(author_id=user_id).count()
    if post_count >= 1:
        if award_achievement(user_id, 'first_post'):
            awarded.append('first_post')
    if post_count >= 10:
        if award_achievement(user_id, 'post_10'):
            awarded.append('post_10')
    if post_count >= 50:
        if award_achievement(user_id, 'post_50'):
            awarded.append('post_50')
    
    follower_count = Follow.query.filter_by(followed_id=user_id).count()
    if follower_count >= 1:
        if award_achievement(user_id, 'first_follower'):
            awarded.append('first_follower')
    if follower_count >= 10:
        if award_achievement(user_id, 'followers_10'):
            awarded.append('followers_10')
    if follower_count >= 50:
        if award_achievement(user_id, 'followers_50'):
            awarded.append('followers_50')
    
    if user.is_verified:
        if award_achievement(user_id, 'verified'):
            awarded.append('verified')
    
    if user.is_premium:
        if award_achievement(user_id, 'premium'):
            awarded.append('premium')
    
    deal_count = DealInterest.query.filter_by(user_id=user_id).count()
    if deal_count >= 1:
        if award_achievement(user_id, 'first_deal'):
            awarded.append('first_deal')
    if deal_count >= 5:
        if award_achievement(user_id, 'deal_5'):
            awarded.append('deal_5')
    
    course_count = CourseEnrollment.query.filter_by(user_id=user_id).count()
    if course_count >= 1:
        if award_achievement(user_id, 'first_course'):
            awarded.append('first_course')
    
    if user.login_streak >= 7:
        if award_achievement(user_id, 'streak_7'):
            awarded.append('streak_7')
    if user.login_streak >= 30:
        if award_achievement(user_id, 'streak_30'):
            awarded.append('streak_30')
    
    return awarded


def get_user_achievements(user_id):
    """Get all achievements for a user"""
    return UserAchievement.query.filter_by(user_id=user_id).order_by(UserAchievement.earned_at.desc()).all()


def get_available_achievements():
    """Get all available achievements"""
    return Achievement.query.filter_by(is_active=True, is_secret=False).order_by(Achievement.tier, Achievement.category).all()
