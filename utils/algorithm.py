"""
Feed Algorithm - Quality + Relevance + Engagement scoring system
Optimized for professional physician investment community
"""
import math
from datetime import datetime, timedelta
from collections import defaultdict


# =============================================================================
# CONFIGURATION
# =============================================================================

# Time decay settings (investment content stays relevant longer than social media)
HALF_LIFE_HOURS = 48  # Posts lose half their time score after 48 hours

# Engagement weights
ENGAGEMENT_WEIGHTS = {
    'like': 1.0,
    'comment': 3.0,      # Discussion is valuable
    'bookmark': 5.0,     # Saves indicate high value
    'share': 4.0,
    'view': 0.01,        # Views have minimal weight
}

# Quality multipliers
QUALITY_BONUSES = {
    'has_media': 0.1,
    'long_content': 0.2,        # >200 characters
    'very_long_content': 0.3,   # >500 characters
    'has_hashtags': 0.1,
    'high_comment_ratio': 0.3,  # Comments/likes > 0.3
    'has_links': 0.1,
}

# Author trust multipliers
AUTHOR_TRUST = {
    'verified': 1.5,
    'premium': 1.2,
    'high_level': 1.3,     # Level 10+
    'expert_level': 1.5,   # Level 20+
    'admin': 1.4,
}

# Personalization boosts (added to final score)
PERSONALIZATION = {
    'same_specialty': 20,
    'following_author': 15,
    'similar_hashtags': 10,
    'interacted_before': 5,
    'same_room': 10,
}

# Feed mixing ratios
FEED_MIX = {
    'algorithmic': 0.7,    # 70% algorithm-sorted
    'chronological': 0.2,  # 20% recent posts (freshness)
    'discovery': 0.1,      # 10% from outside user's bubble
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def calculate_engagement_score(post):
    """
    Calculate raw engagement score based on interactions
    Returns: float (0-100+ scale)
    """
    score = 0
    
    # Direct engagement metrics
    score += post.upvotes * ENGAGEMENT_WEIGHTS['like']
    score += post.comment_count * ENGAGEMENT_WEIGHTS['comment']
    score += getattr(post, 'bookmark_count', 0) * ENGAGEMENT_WEIGHTS['bookmark']
    score += getattr(post, 'share_count', 0) * ENGAGEMENT_WEIGHTS['share']
    score += post.view_count * ENGAGEMENT_WEIGHTS['view']
    
    # Normalize to roughly 0-100 scale for typical posts
    # Top posts can exceed 100
    return score


def calculate_quality_multiplier(post):
    """
    Calculate quality multiplier based on content characteristics
    Returns: float (1.0 - 2.0)
    """
    multiplier = 1.0
    
    content = post.content or ''
    
    # Content length bonus
    if len(content) > 500:
        multiplier += QUALITY_BONUSES['very_long_content']
    elif len(content) > 200:
        multiplier += QUALITY_BONUSES['long_content']
    
    # Media bonus
    if post.media_count > 0:
        multiplier += QUALITY_BONUSES['has_media']
    
    # Hashtags bonus
    if '#' in content:
        multiplier += QUALITY_BONUSES['has_hashtags']
    
    # High comment-to-like ratio (indicates discussion)
    if post.upvotes > 0:
        comment_ratio = post.comment_count / post.upvotes
        if comment_ratio > 0.3:
            multiplier += QUALITY_BONUSES['high_comment_ratio']
    
    # Links bonus (sharing resources)
    if 'http' in content.lower() or 'www.' in content.lower():
        multiplier += QUALITY_BONUSES['has_links']
    
    # Cap at 2.0
    return min(multiplier, 2.0)


def calculate_author_trust(author):
    """
    Calculate author trust multiplier based on reputation
    Returns: float (1.0 - 3.0)
    """
    multiplier = 1.0
    
    if author.is_verified:
        multiplier *= AUTHOR_TRUST['verified']
    
    if author.is_premium:
        multiplier *= AUTHOR_TRUST['premium']
    
    if author.level >= 20:
        multiplier *= AUTHOR_TRUST['expert_level']
    elif author.level >= 10:
        multiplier *= AUTHOR_TRUST['high_level']
    
    if author.is_admin:
        multiplier *= AUTHOR_TRUST['admin']
    
    # Cap at 3.0
    return min(multiplier, 3.0)


def calculate_time_decay(post):
    """
    Calculate time decay factor using exponential decay
    Half-life of 48 hours means post loses half its score after 2 days
    Returns: float (0.0 - 1.0)
    """
    now = datetime.utcnow()
    age_hours = (now - post.created_at).total_seconds() / 3600
    
    # Exponential decay: score = e^(-λt) where λ = ln(2)/half_life
    decay_constant = math.log(2) / HALF_LIFE_HOURS
    decay_factor = math.exp(-decay_constant * age_hours)
    
    # Minimum decay of 0.05 (posts never completely disappear)
    return max(decay_factor, 0.05)


def calculate_personalization_boost(post, user, user_interests=None):
    """
    Calculate personalization boost based on user preferences
    Returns: float (0 - 50)
    """
    if user_interests is None:
        user_interests = {}
    
    boost = 0
    author = post.author
    
    # Same specialty
    if user.specialty and author.specialty == user.specialty:
        boost += PERSONALIZATION['same_specialty']
    
    # Following author
    if user_interests.get('following_ids') and author.id in user_interests['following_ids']:
        boost += PERSONALIZATION['following_author']
    
    # Similar hashtags (user has engaged with same hashtags before)
    post_hashtags = set(user_interests.get('post_hashtags', {}).get(post.id, []))
    user_hashtags = set(user_interests.get('engaged_hashtags', []))
    if post_hashtags & user_hashtags:
        boost += PERSONALIZATION['similar_hashtags']
    
    # Has interacted with this author before
    if user_interests.get('interacted_authors') and author.id in user_interests['interacted_authors']:
        boost += PERSONALIZATION['interacted_before']
    
    # Same room preference
    if post.room_id and user_interests.get('favorite_rooms') and post.room_id in user_interests['favorite_rooms']:
        boost += PERSONALIZATION['same_room']
    
    return boost


def calculate_post_score(post, user=None, user_interests=None):
    """
    Calculate final score for a post
    
    Formula: (Engagement × Quality × Author Trust) × Time Decay + Personalization
    
    Returns: float
    """
    # Skip anonymous posts for author trust (use neutral 1.0)
    if post.is_anonymous:
        author_trust = 1.0
    else:
        author_trust = calculate_author_trust(post.author)
    
    engagement = calculate_engagement_score(post)
    quality = calculate_quality_multiplier(post)
    time_decay = calculate_time_decay(post)
    
    # Base score
    base_score = engagement * quality * author_trust * time_decay
    
    # Add personalization if user provided
    if user:
        personalization = calculate_personalization_boost(post, user, user_interests)
        base_score += personalization
    
    return base_score


# =============================================================================
# BATCH SCORING FOR FEED GENERATION
# =============================================================================

def score_posts_batch(posts, user=None, user_interests=None):
    """
    Score multiple posts and return sorted by score
    Returns: list of (post, score) tuples, sorted descending
    """
    scored = []
    
    for post in posts:
        score = calculate_post_score(post, user, user_interests)
        scored.append((post, score))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return scored


def get_user_interests(user, db):
    """
    Gather user interest data for personalization
    Returns: dict with interest data
    """
    from models import UserFollow, PostVote, Bookmark, PostHashtag, Post
    
    interests = {
        'following_ids': set(),
        'interacted_authors': set(),
        'engaged_hashtags': set(),
        'favorite_rooms': set(),
        'post_hashtags': {},
    }
    
    # Get users this person follows
    follows = UserFollow.query.filter_by(follower_id=user.id).all()
    interests['following_ids'] = {f.following_id for f in follows}
    
    # Get authors user has interacted with (liked, commented, bookmarked)
    voted_posts = db.session.query(Post.user_id).join(PostVote).filter(
        PostVote.user_id == user.id
    ).distinct().all()
    interests['interacted_authors'] = {p[0] for p in voted_posts}
    
    # Get hashtags user has engaged with
    from models import Hashtag
    user_post_ids = db.session.query(PostVote.post_id).filter_by(user_id=user.id).all()
    user_post_ids = [p[0] for p in user_post_ids]
    
    if user_post_ids:
        hashtag_links = PostHashtag.query.filter(PostHashtag.post_id.in_(user_post_ids)).all()
        hashtag_ids = {h.hashtag_id for h in hashtag_links}
        if hashtag_ids:
            hashtags = Hashtag.query.filter(Hashtag.id.in_(hashtag_ids)).all()
            interests['engaged_hashtags'] = {h.name for h in hashtags}
    
    # Get favorite rooms (rooms user posts/comments in most)
    from models import Comment
    user_room_posts = db.session.query(Post.room_id, db.func.count(Post.id))\
        .filter(Post.user_id == user.id, Post.room_id.isnot(None))\
        .group_by(Post.room_id)\
        .order_by(db.func.count(Post.id).desc())\
        .limit(5).all()
    interests['favorite_rooms'] = {r[0] for r in user_room_posts}
    
    return interests


# =============================================================================
# FEED GENERATION
# =============================================================================

def generate_feed(user, db, page=1, per_page=20, include_discovery=True):
    """
    Generate personalized feed for user using the algorithm
    
    Mix:
    - 70% algorithmic (scored by engagement + quality + personalization)
    - 20% chronological (ensure freshness)
    - 10% discovery (posts outside user's bubble)
    
    Returns: list of posts
    """
    from models import Post, UserFollow
    
    # Get user interests for personalization
    user_interests = get_user_interests(user, db)
    
    # Calculate how many posts for each category
    algorithmic_count = int(per_page * FEED_MIX['algorithmic'])
    chronological_count = int(per_page * FEED_MIX['chronological'])
    discovery_count = per_page - algorithmic_count - chronological_count
    
    # Time window for feed (don't show posts older than 7 days unless exceptional)
    time_cutoff = datetime.utcnow() - timedelta(days=7)
    
    # Base query - non-deleted posts from last 7 days
    base_query = Post.query.filter(Post.created_at >= time_cutoff)
    
    # Get all candidate posts
    all_posts = base_query.all()
    
    # Score all posts
    scored_posts = score_posts_batch(all_posts, user, user_interests)
    
    # Get top algorithmic posts
    algorithmic_posts = [p for p, s in scored_posts[:algorithmic_count * 2]]
    
    # Get chronological posts (most recent, not already in algorithmic)
    algorithmic_ids = {p.id for p in algorithmic_posts}
    chronological_posts = Post.query.filter(
        Post.created_at >= time_cutoff,
        ~Post.id.in_(algorithmic_ids)
    ).order_by(Post.created_at.desc()).limit(chronological_count).all()
    
    # Discovery posts (from specialties/rooms user doesn't usually engage with)
    following_ids = user_interests['following_ids']
    favorite_rooms = user_interests['favorite_rooms']
    
    discovery_posts = []
    if include_discovery:
        discovery_query = Post.query.filter(
            Post.created_at >= time_cutoff,
            ~Post.id.in_(algorithmic_ids),
            ~Post.id.in_([p.id for p in chronological_posts])
        )
        
        # Exclude own specialty and favorite rooms for discovery
        if user.specialty:
            # This is simplified - ideally filter by author specialty
            pass
        
        if favorite_rooms:
            discovery_query = discovery_query.filter(
                db.or_(Post.room_id.is_(None), ~Post.room_id.in_(favorite_rooms))
            )
        
        discovery_posts = discovery_query.order_by(db.func.random()).limit(discovery_count).all()
    
    # Combine and interleave
    feed = []
    algo_idx, chrono_idx, disc_idx = 0, 0, 0
    
    for i in range(per_page):
        # Interleave based on ratio
        if i % 10 < 7 and algo_idx < len(algorithmic_posts):
            feed.append(algorithmic_posts[algo_idx])
            algo_idx += 1
        elif i % 10 < 9 and chrono_idx < len(chronological_posts):
            feed.append(chronological_posts[chrono_idx])
            chrono_idx += 1
        elif disc_idx < len(discovery_posts):
            feed.append(discovery_posts[disc_idx])
            disc_idx += 1
        elif algo_idx < len(algorithmic_posts):
            feed.append(algorithmic_posts[algo_idx])
            algo_idx += 1
    
    # Pagination (simplified - in production, use cursor-based)
    start = (page - 1) * per_page
    end = start + per_page
    
    return feed[:per_page]


# =============================================================================
# PRE-CALCULATED SCORES (for background job)
# =============================================================================

def update_post_scores(db):
    """
    Background job to pre-calculate and cache post scores
    Should run every 15-30 minutes
    """
    from models import Post, PostScore
    
    # Get posts from last 7 days
    time_cutoff = datetime.utcnow() - timedelta(days=7)
    posts = Post.query.filter(Post.created_at >= time_cutoff).all()
    
    for post in posts:
        # Calculate base score (without personalization)
        score = calculate_post_score(post, user=None)
        
        # Update or create score record
        post_score = PostScore.query.filter_by(post_id=post.id).first()
        
        if post_score:
            post_score.score = score
            post_score.updated_at = datetime.utcnow()
        else:
            post_score = PostScore(
                post_id=post.id,
                score=score,
                engagement_score=calculate_engagement_score(post),
                quality_score=calculate_quality_multiplier(post),
                decay_score=calculate_time_decay(post)
            )
            db.session.add(post_score)
    
    db.session.commit()
    return len(posts)


def get_trending_posts(db, limit=10, hours=24):
    """
    Get trending posts based on recent velocity of engagement
    Uses engagement gained in last X hours vs previous period
    """
    from models import Post, PostScore
    
    # Get top scored posts from last 24 hours
    time_cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    trending = Post.query.filter(
        Post.created_at >= time_cutoff
    ).join(PostScore).order_by(
        PostScore.score.desc()
    ).limit(limit).all()
    
    return trending


def get_posts_for_specialty(specialty, db, limit=20):
    """
    Get top posts relevant to a specific specialty
    """
    from models import Post, User, PostScore
    
    # Posts by authors in this specialty
    posts = Post.query.join(User).filter(
        User.specialty == specialty,
        Post.is_anonymous == False
    ).order_by(Post.created_at.desc()).limit(limit).all()
    
    # Score and sort
    scored = score_posts_batch(posts)
    
    return [p for p, s in scored[:limit]]
