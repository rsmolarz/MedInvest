"""
Feed Ranking Algorithm for MedInvest
Implements engagement, relevance, and personalization scoring for feed content
"""
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RankingWeights:
    """Configurable weights for ranking algorithm"""
    LIKE_WEIGHT: float = 1.0
    COMMENT_WEIGHT: float = 2.0
    SHARE_WEIGHT: float = 3.0
    SAVE_WEIGHT: float = 1.5
    
    FOLLOW_BONUS: float = 0.3
    SAME_SPECIALTY_BONUS: float = 0.2
    VERIFIED_AUTHOR_BONUS: float = 0.15
    
    ENGAGEMENT_WEIGHT: float = 0.4
    RELEVANCE_WEIGHT: float = 0.35
    PERSONALIZATION_WEIGHT: float = 0.25
    
    TIME_DECAY_HOURS: float = 24.0
    RECENCY_BOOST_HOURS: float = 4.0


class FeedRankingService:
    """
    Service for calculating feed ranking scores.
    Combines engagement, relevance, and personalization for optimal content ordering.
    """
    
    def __init__(self, weights: RankingWeights = None):
        self.weights = weights or RankingWeights()
        self._user_interests_cache: Dict[int, Set[str]] = {}
        self._user_following_cache: Dict[int, Set[int]] = {}
    
    def calculate_engagement_score(
        self, 
        post_id: int, 
        hours_old: float,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        saves: int = 0
    ) -> float:
        """
        Calculate engagement score based on interactions and time decay.
        
        Formula: (likes + comments*2 + shares*3 + saves*1.5) * decay_factor
        decay_factor = 1 / (1 + hours_old/24)
        
        Args:
            post_id: Post identifier
            hours_old: Hours since post was created
            likes: Number of likes
            comments: Number of comments
            shares: Number of shares
            saves: Number of saves/bookmarks
        
        Returns:
            Engagement score (float, higher = more engaging)
        """
        raw_engagement = (
            likes * self.weights.LIKE_WEIGHT +
            comments * self.weights.COMMENT_WEIGHT +
            shares * self.weights.SHARE_WEIGHT +
            saves * self.weights.SAVE_WEIGHT
        )
        
        decay_factor = 1 / (1 + hours_old / self.weights.TIME_DECAY_HOURS)
        
        recency_boost = 1.0
        if hours_old < self.weights.RECENCY_BOOST_HOURS:
            recency_boost = 1.5 - (hours_old / self.weights.RECENCY_BOOST_HOURS * 0.5)
        
        score = raw_engagement * decay_factor * recency_boost
        
        logger.debug(
            f"Post {post_id} engagement: raw={raw_engagement:.2f}, "
            f"decay={decay_factor:.3f}, boost={recency_boost:.2f}, final={score:.2f}"
        )
        
        return score
    
    def calculate_relevance_score(
        self, 
        user_id: int, 
        post: Dict[str, Any],
        user_interests: Set[str] = None
    ) -> float:
        """
        Calculate relevance score based on user interests matching post tags.
        
        Formula: match_count / total_tags (0-1 scale)
        
        Args:
            user_id: User identifier
            post: Post data containing 'hashtags' or 'tags'
            user_interests: Optional set of user interest tags
        
        Returns:
            Relevance score (0.0 to 1.0)
        """
        if user_interests is None:
            user_interests = self._get_user_interests(user_id)
        
        if not user_interests:
            return 0.5
        
        post_tags = set()
        if 'hashtags' in post and post['hashtags']:
            if isinstance(post['hashtags'], list):
                post_tags.update(tag.lower().strip('#') for tag in post['hashtags'])
            elif isinstance(post['hashtags'], str):
                post_tags.update(tag.lower().strip('#') for tag in post['hashtags'].split(','))
        
        if 'tags' in post and post['tags']:
            if isinstance(post['tags'], list):
                post_tags.update(tag.lower() for tag in post['tags'])
        
        if 'category' in post and post['category']:
            post_tags.add(post['category'].lower())
        
        if not post_tags:
            return 0.5
        
        user_interests_lower = {i.lower() for i in user_interests}
        matches = post_tags.intersection(user_interests_lower)
        match_count = len(matches)
        
        relevance = match_count / len(post_tags)
        
        logger.debug(
            f"User {user_id} relevance for post: "
            f"matches={match_count}/{len(post_tags)}, score={relevance:.3f}"
        )
        
        return min(relevance, 1.0)
    
    def calculate_personalization_score(
        self, 
        user_id: int, 
        post_author_id: int,
        user_following: Set[int] = None,
        user_specialty: str = None,
        author_specialty: str = None,
        author_verified: bool = False
    ) -> float:
        """
        Calculate personalization score using collaborative filtering signals.
        
        Factors:
        - Following relationship: +0.3 if user follows author
        - Same specialty: +0.2 if same medical specialty
        - Verified author: +0.15 if author is verified
        
        Args:
            user_id: Current user identifier
            post_author_id: Post author identifier
            user_following: Optional set of user IDs the user follows
            user_specialty: Current user's medical specialty
            author_specialty: Post author's medical specialty
            author_verified: Whether post author is verified
        
        Returns:
            Personalization score (0.0 to 1.0)
        """
        score = 0.0
        
        if user_following is None:
            user_following = self._get_user_following(user_id)
        
        if post_author_id in user_following:
            score += self.weights.FOLLOW_BONUS
        
        if user_specialty and author_specialty:
            if user_specialty.lower() == author_specialty.lower():
                score += self.weights.SAME_SPECIALTY_BONUS
        
        if author_verified:
            score += self.weights.VERIFIED_AUTHOR_BONUS
        
        logger.debug(
            f"User {user_id} personalization for author {post_author_id}: "
            f"score={score:.3f}"
        )
        
        return min(score, 1.0)
    
    def calculate_combined_score(
        self,
        user_id: int,
        post: Dict[str, Any],
        user_interests: Set[str] = None,
        user_following: Set[int] = None,
        user_specialty: str = None
    ) -> float:
        """
        Calculate combined ranking score using all factors.
        
        Formula: 
        score = (engagement * 0.4) + (relevance * 0.35) + (personalization * 0.25)
        
        Args:
            user_id: Current user identifier
            post: Post data dictionary
            user_interests: Optional cached user interests
            user_following: Optional cached user following set
            user_specialty: Optional user's medical specialty
        
        Returns:
            Combined ranking score
        """
        created_at = post.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        elif created_at is None:
            created_at = datetime.utcnow()
        
        hours_old = (datetime.utcnow() - created_at.replace(tzinfo=None)).total_seconds() / 3600
        
        engagement_score = self.calculate_engagement_score(
            post_id=post.get('id', 0),
            hours_old=hours_old,
            likes=post.get('like_count', 0) or post.get('likes', 0),
            comments=post.get('comment_count', 0) or post.get('comments', 0),
            shares=post.get('share_count', 0) or post.get('shares', 0),
            saves=post.get('save_count', 0) or post.get('saves', 0) or post.get('bookmarks', 0)
        )
        
        relevance_score = self.calculate_relevance_score(
            user_id=user_id,
            post=post,
            user_interests=user_interests
        )
        
        personalization_score = self.calculate_personalization_score(
            user_id=user_id,
            post_author_id=post.get('author_id') or post.get('user_id', 0),
            user_following=user_following,
            user_specialty=user_specialty,
            author_specialty=post.get('author_specialty'),
            author_verified=post.get('author_verified', False)
        )
        
        combined = (
            engagement_score * self.weights.ENGAGEMENT_WEIGHT +
            relevance_score * self.weights.RELEVANCE_WEIGHT +
            personalization_score * self.weights.PERSONALIZATION_WEIGHT
        )
        
        return combined
    
    def rank_posts(
        self,
        user_id: int,
        posts: List[Dict[str, Any]],
        user_interests: Set[str] = None,
        user_following: Set[int] = None,
        user_specialty: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Rank a list of posts for a specific user.
        
        Args:
            user_id: Current user identifier
            posts: List of post dictionaries
            user_interests: Optional cached user interests
            user_following: Optional cached user following set
            user_specialty: Optional user's medical specialty
            limit: Maximum posts to return
        
        Returns:
            Sorted list of posts with ranking scores
        """
        if not posts:
            return []
        
        if user_interests is None:
            user_interests = self._get_user_interests(user_id)
        if user_following is None:
            user_following = self._get_user_following(user_id)
        
        scored_posts = []
        for post in posts:
            score = self.calculate_combined_score(
                user_id=user_id,
                post=post,
                user_interests=user_interests,
                user_following=user_following,
                user_specialty=user_specialty
            )
            post_with_score = post.copy()
            post_with_score['_ranking_score'] = score
            scored_posts.append(post_with_score)
        
        ranked = sorted(scored_posts, key=lambda p: p['_ranking_score'], reverse=True)
        
        if limit:
            ranked = ranked[:limit]
        
        logger.info(f"Ranked {len(ranked)} posts for user {user_id}")
        
        return ranked
    
    def _get_user_interests(self, user_id: int) -> Set[str]:
        """Get user interests from cache or database"""
        if user_id in self._user_interests_cache:
            return self._user_interests_cache[user_id]
        
        try:
            from app import db
            from models import User, UserInterest
            
            interests = set()
            user = db.session.get(User, user_id)
            if user:
                if hasattr(user, 'specialty') and user.specialty:
                    interests.add(user.specialty.lower())
                if hasattr(user, 'interests'):
                    user_interests = UserInterest.query.filter_by(user_id=user_id).all()
                    for ui in user_interests:
                        if hasattr(ui, 'interest') and ui.interest:
                            interests.add(ui.interest.lower())
            
            self._user_interests_cache[user_id] = interests
            return interests
        except Exception as e:
            logger.warning(f"Could not load user interests: {e}")
            return set()
    
    def _get_user_following(self, user_id: int) -> Set[int]:
        """Get users that user_id follows from cache or database"""
        if user_id in self._user_following_cache:
            return self._user_following_cache[user_id]
        
        try:
            from app import db
            from models import Follow
            
            following = set()
            follows = Follow.query.filter_by(follower_id=user_id).all()
            for f in follows:
                following.add(f.followed_id)
            
            self._user_following_cache[user_id] = following
            return following
        except Exception as e:
            logger.warning(f"Could not load user following: {e}")
            return set()
    
    def clear_user_cache(self, user_id: int):
        """Clear cached data for a specific user"""
        self._user_interests_cache.pop(user_id, None)
        self._user_following_cache.pop(user_id, None)
    
    def clear_all_caches(self):
        """Clear all cached user data"""
        self._user_interests_cache.clear()
        self._user_following_cache.clear()


_feed_ranking_service = None


def get_feed_ranking_service() -> FeedRankingService:
    """Get singleton instance of FeedRankingService"""
    global _feed_ranking_service
    if _feed_ranking_service is None:
        _feed_ranking_service = FeedRankingService()
    return _feed_ranking_service


def rank_feed_for_user(
    user_id: int, 
    posts: List[Dict[str, Any]], 
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to rank posts for a user.
    
    Args:
        user_id: User to rank posts for
        posts: List of post dictionaries
        limit: Maximum posts to return
    
    Returns:
        Ranked list of posts
    """
    service = get_feed_ranking_service()
    return service.rank_posts(user_id, posts, limit=limit)
