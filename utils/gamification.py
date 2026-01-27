"""
Gamification Service - Points, Levels, Leaderboards, and Streaks
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from app import db
from utils.cache_service import CacheService

logger = logging.getLogger(__name__)

POINT_VALUES = {
    'post_created': 5,
    'comment_added': 3,
    'like_received': 1,
    'like_given': 1,
    'share': 5,
    'bookmark': 2,
    'daily_login': 2,
    'streak_bonus_7': 10,
    'streak_bonus_30': 50,
    'referral_signup': 25,
    'deal_interest': 5,
    'course_enrollment': 10,
    'course_completion': 50,
    'ama_question': 3,
    'verification_complete': 100,
    'profile_complete': 20,
}

LEVEL_THRESHOLDS = {
    'bronze': (0, 100),
    'silver': (100, 500),
    'gold': (500, 1500),
    'platinum': (1500, 5000),
    'diamond': (5000, float('inf')),
}

LEVEL_NAMES = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']


class GamificationService:
    """Core gamification logic"""
    
    @staticmethod
    def get_level_name(points: int) -> str:
        """Get level name based on points"""
        for level_name, (min_pts, max_pts) in LEVEL_THRESHOLDS.items():
            if min_pts <= points < max_pts:
                return level_name.capitalize()
        return 'Diamond'
    
    @staticmethod
    def get_level_number(points: int) -> int:
        """Get numeric level (1-5) based on points"""
        for i, (level_name, (min_pts, max_pts)) in enumerate(LEVEL_THRESHOLDS.items(), 1):
            if min_pts <= points < max_pts:
                return i
        return 5
    
    @staticmethod
    def get_progress_to_next_level(points: int) -> Dict[str, Any]:
        """Get progress percentage to next level"""
        current_level = GamificationService.get_level_name(points)
        
        for i, (level_name, (min_pts, max_pts)) in enumerate(LEVEL_THRESHOLDS.items()):
            if min_pts <= points < max_pts:
                if max_pts == float('inf'):
                    return {
                        'current_level': current_level,
                        'next_level': None,
                        'progress': 100,
                        'points_needed': 0,
                        'current_points': points
                    }
                
                progress = ((points - min_pts) / (max_pts - min_pts)) * 100
                next_level_name = list(LEVEL_THRESHOLDS.keys())[i + 1].capitalize()
                
                return {
                    'current_level': current_level,
                    'next_level': next_level_name,
                    'progress': round(progress, 1),
                    'points_needed': max_pts - points,
                    'current_points': points
                }
        
        return {
            'current_level': 'Diamond',
            'next_level': None,
            'progress': 100,
            'points_needed': 0,
            'current_points': points
        }
    
    @staticmethod
    def award_points(user_id: int, action: str, reference_type: str = None, reference_id: int = None) -> int:
        """Award points for an action and log the transaction"""
        from models import User, PointTransaction, UserPoints
        
        points = POINT_VALUES.get(action, 0)
        if points == 0:
            return 0
        
        try:
            user = User.query.get(user_id)
            if not user:
                return 0
            
            user.add_points(points)
            
            transaction = PointTransaction(
                user_id=user_id,
                points=points,
                action=action,
                reference_type=reference_type,
                reference_id=reference_id
            )
            db.session.add(transaction)
            
            user_points = UserPoints.query.filter_by(user_id=user_id).first()
            if user_points:
                user_points.total_points = (user_points.total_points or 0) + points
                user_points.weekly_points = (user_points.weekly_points or 0) + points
                user_points.monthly_points = (user_points.monthly_points or 0) + points
                user_points.level = GamificationService.get_level_number(user_points.total_points)
            else:
                user_points = UserPoints(
                    user_id=user_id,
                    total_points=points,
                    weekly_points=points,
                    monthly_points=points,
                    level=1
                )
                db.session.add(user_points)
            
            db.session.commit()
            
            CacheService.delete(f'leaderboard:weekly')
            CacheService.delete(f'leaderboard:monthly')
            CacheService.delete(f'leaderboard:alltime')
            
            logger.info(f"Awarded {points} points to user {user_id} for {action}")
            return points
            
        except Exception as e:
            logger.error(f"Error awarding points: {e}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def update_streak(user_id: int) -> Dict[str, Any]:
        """Update user's login streak"""
        from models import User, UserPoints
        
        try:
            user = User.query.get(user_id)
            if not user:
                return {'streak': 0, 'bonus': 0}
            
            today = date.today()
            user_points = UserPoints.query.filter_by(user_id=user_id).first()
            
            if not user_points:
                user_points = UserPoints(user_id=user_id, streak_days=1, last_activity_date=today)
                db.session.add(user_points)
                db.session.commit()
                return {'streak': 1, 'bonus': 0}
            
            last_activity = user_points.last_activity_date
            
            if last_activity == today:
                return {'streak': user_points.streak_days, 'bonus': 0}
            
            bonus = 0
            
            if last_activity == today - timedelta(days=1):
                user_points.streak_days += 1
                
                if user_points.streak_days == 7:
                    bonus = POINT_VALUES['streak_bonus_7']
                    GamificationService.award_points(user_id, 'streak_bonus_7')
                elif user_points.streak_days == 30:
                    bonus = POINT_VALUES['streak_bonus_30']
                    GamificationService.award_points(user_id, 'streak_bonus_30')
            else:
                user_points.streak_days = 1
            
            user_points.last_activity_date = today
            
            if user.login_streak is not None:
                user.login_streak = user_points.streak_days
            
            db.session.commit()
            
            GamificationService.award_points(user_id, 'daily_login')
            
            return {
                'streak': user_points.streak_days,
                'bonus': bonus
            }
            
        except Exception as e:
            logger.error(f"Error updating streak: {e}")
            db.session.rollback()
            return {'streak': 0, 'bonus': 0}
    
    @staticmethod
    def get_leaderboard(period: str = 'weekly', limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard for a time period"""
        from models import User, UserPoints
        
        cache_key = f'leaderboard:{period}:{limit}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached
        
        try:
            if period == 'weekly':
                query = db.session.query(User, UserPoints).join(
                    UserPoints, User.id == UserPoints.user_id
                ).order_by(UserPoints.weekly_points.desc()).limit(limit)
            elif period == 'monthly':
                query = db.session.query(User, UserPoints).join(
                    UserPoints, User.id == UserPoints.user_id
                ).order_by(UserPoints.monthly_points.desc()).limit(limit)
            else:
                query = db.session.query(User, UserPoints).join(
                    UserPoints, User.id == UserPoints.user_id
                ).order_by(UserPoints.total_points.desc()).limit(limit)
            
            results = query.all()
            
            leaderboard = []
            for rank, (user, points) in enumerate(results, 1):
                leaderboard.append({
                    'rank': rank,
                    'user_id': user.id,
                    'name': user.full_name,
                    'specialty': user.specialty,
                    'is_verified': user.is_verified,
                    'points': getattr(points, f'{period}_points' if period != 'alltime' else 'total_points', 0),
                    'level': GamificationService.get_level_name(points.total_points or 0),
                    'streak': points.streak_days or 0
                })
            
            CacheService.set(cache_key, leaderboard, ttl=300)
            return leaderboard
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    @staticmethod
    def get_user_rank(user_id: int, period: str = 'weekly') -> Optional[int]:
        """Get user's rank on the leaderboard"""
        from models import UserPoints
        from sqlalchemy import func
        
        try:
            user_points = UserPoints.query.filter_by(user_id=user_id).first()
            if not user_points:
                return None
            
            if period == 'weekly':
                user_score = user_points.weekly_points or 0
                higher_count = UserPoints.query.filter(
                    UserPoints.weekly_points > user_score
                ).count()
            elif period == 'monthly':
                user_score = user_points.monthly_points or 0
                higher_count = UserPoints.query.filter(
                    UserPoints.monthly_points > user_score
                ).count()
            else:
                user_score = user_points.total_points or 0
                higher_count = UserPoints.query.filter(
                    UserPoints.total_points > user_score
                ).count()
            
            return higher_count + 1
            
        except Exception as e:
            logger.error(f"Error getting user rank: {e}")
            return None
    
    @staticmethod
    def get_top_mentors(limit: int = 5) -> List[Dict[str, Any]]:
        """Get top mentors by mentorship session count"""
        from models import User, MentorshipSession
        from sqlalchemy import func
        
        cache_key = f'top_mentors:{limit}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached
        
        try:
            results = db.session.query(
                User,
                func.count(MentorshipSession.id).label('session_count')
            ).join(
                MentorshipSession, User.id == MentorshipSession.mentor_id
            ).filter(
                MentorshipSession.status == 'completed'
            ).group_by(User.id).order_by(
                func.count(MentorshipSession.id).desc()
            ).limit(limit).all()
            
            mentors = []
            for user, session_count in results:
                mentors.append({
                    'user_id': user.id,
                    'name': user.full_name,
                    'specialty': user.specialty,
                    'is_verified': user.is_verified,
                    'session_count': session_count,
                    'level': GamificationService.get_level_name(user.points or 0)
                })
            
            CacheService.set(cache_key, mentors, ttl=3600)
            return mentors
            
        except Exception as e:
            logger.error(f"Error getting top mentors: {e}")
            return []
    
    @staticmethod
    def reset_weekly_points():
        """Reset weekly points (run via scheduled job)"""
        from models import UserPoints
        
        try:
            UserPoints.query.update({UserPoints.weekly_points: 0})
            db.session.commit()
            CacheService.delete_pattern('leaderboard:weekly*')
            logger.info("Weekly points reset completed")
        except Exception as e:
            logger.error(f"Error resetting weekly points: {e}")
            db.session.rollback()
    
    @staticmethod
    def reset_monthly_points():
        """Reset monthly points (run via scheduled job)"""
        from models import UserPoints
        
        try:
            UserPoints.query.update({UserPoints.monthly_points: 0})
            db.session.commit()
            CacheService.delete_pattern('leaderboard:monthly*')
            logger.info("Monthly points reset completed")
        except Exception as e:
            logger.error(f"Error resetting monthly points: {e}")
            db.session.rollback()
