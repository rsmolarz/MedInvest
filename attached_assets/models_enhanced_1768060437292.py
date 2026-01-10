"""
Enhanced models for MedInvest Platform
Adds: Anonymous posting, Achievement badges, Specialty rooms, Trending topics
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


# ============================================================================
# EXISTING MODELS (keeping all original functionality)
# ============================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    medical_license = db.Column(db.String(50), unique=True, nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    hospital_affiliation = db.Column(db.String(200))
    bio = db.Column(db.Text)
    profile_image_url = db.Column(db.String(500))
    location = db.Column(db.String(100))
    years_of_experience = db.Column(db.Integer)
    investment_interests = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    account_active = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NEW: Points for gamification
    points = db.Column(db.Integer, default=0)
    
    # Relationships
    progress = db.relationship('UserProgress', back_populates='user', lazy='dynamic')
    forum_posts = db.relationship('ForumPost', back_populates='author', lazy='dynamic')
    transactions = db.relationship('PortfolioTransaction', back_populates='user', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    likes = db.relationship('Like', back_populates='user', lazy='dynamic')
    
    # NEW relationships
    achievements = db.relationship('UserAchievement', back_populates='user', lazy='dynamic')
    room_memberships = db.relationship('RoomMembership', back_populates='user', lazy='dynamic')
    
    # Following relationships
    following = db.relationship('Follow', 
                               foreign_keys='Follow.follower_id',
                               backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    
    followers = db.relationship('Follow',
                               foreign_keys='Follow.following_id', 
                               backref=db.backref('following', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def follow(self, user):
        if not self.is_following(user):
            follow = Follow()
            follow.follower_id = self.id
            follow.following_id = user.id
            db.session.add(follow)
    
    def unfollow(self, user):
        follow = self.following.filter_by(following_id=user.id).first()
        if follow:
            db.session.delete(follow)
    
    def is_following(self, user):
        return self.following.filter_by(following_id=user.id).first() is not None
    
    def followers_count(self):
        return self.followers.count()
    
    def following_count(self):
        return self.following.count()
    
    def get_feed_posts(self):
        following_ids = [f.following_id for f in self.following.all()]
        following_ids.append(self.id)
        return Post.query.filter(Post.author_id.in_(following_ids)).order_by(Post.created_at.desc())
    
    # NEW: Achievement methods
    def award_achievement(self, achievement_id):
        """Award an achievement to the user"""
        if not self.has_achievement(achievement_id):
            ua = UserAchievement(user_id=self.id, achievement_id=achievement_id)
            db.session.add(ua)
            achievement = Achievement.query.get(achievement_id)
            if achievement:
                self.points += achievement.points
            return True
        return False
    
    def has_achievement(self, achievement_id):
        """Check if user has a specific achievement"""
        return self.achievements.filter_by(achievement_id=achievement_id).first() is not None


class Module(db.Model):
    __tablename__ = 'modules'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)
    estimated_duration = db.Column(db.Integer)
    category = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    progress = db.relationship('UserProgress', back_populates='module', lazy='dynamic')


class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completion_date = db.Column(db.DateTime)
    time_spent = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', back_populates='progress')
    module = db.relationship('Module', back_populates='progress')


class ForumTopic(db.Model):
    __tablename__ = 'forum_topics'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    posts = db.relationship('ForumPost', back_populates='topic', lazy='dynamic')


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topics.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    topic = db.relationship('ForumTopic', back_populates='posts')
    author = db.relationship('User', back_populates='forum_posts')
    replies = db.relationship('ForumPost', backref='parent', remote_side=[id])


class PortfolioTransaction(db.Model):
    __tablename__ = 'portfolio_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='transactions')


class Resource(db.Model):
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    resource_type = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    post_type = db.Column(db.String(20), default='general')
    tags = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, default=True)
    
    # NEW: Anonymous posting support
    is_anonymous = db.Column(db.Boolean, default=False)
    anonymous_name = db.Column(db.String(100))  # e.g., "Cardiologist in CA"
    
    # NEW: Room/specialty association
    room_id = db.Column(db.Integer, db.ForeignKey('investment_rooms.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = db.relationship('User', back_populates='posts')
    comments = db.relationship('Comment', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    room = db.relationship('InvestmentRoom', back_populates='posts')
    
    def likes_count(self):
        return self.likes.count()
    
    def comments_count(self):
        return self.comments.count()
    
    def is_liked_by(self, user):
        return self.likes.filter_by(user_id=user.id).first() is not None
    
    def get_display_name(self):
        """Get the display name for the post (either real name or anonymous)"""
        if self.is_anonymous:
            return self.anonymous_name or "Anonymous MD"
        return self.author.full_name


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    content = db.Column(db.Text, nullable=False)
    
    # NEW: Anonymous commenting
    is_anonymous = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    post = db.relationship('Post', back_populates='comments')
    author = db.relationship('User', back_populates='comments')
    replies = db.relationship('Comment', backref='parent', remote_side=[id])


class Like(db.Model):
    __tablename__ = 'likes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='likes')
    post = db.relationship('Post', back_populates='likes')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)


class Follow(db.Model):
    __tablename__ = 'follows'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('follower_id', 'following_id', name='unique_follow_relationship'),)


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notification_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    related_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    sender = db.relationship('User', foreign_keys=[sender_id])
    related_post = db.relationship('Post')


# ============================================================================
# NEW MODELS FOR ENHANCED FEATURES
# ============================================================================

class InvestmentRoom(db.Model):
    """Specialty-specific investment discussion rooms"""
    __tablename__ = 'investment_rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    # Room type: 'specialty', 'career_stage', 'topic', 'location'
    room_type = db.Column(db.String(50), default='specialty')
    
    # For specialty rooms: matches User.specialty
    specialty = db.Column(db.String(100))
    
    # Icon/image for the room
    icon = db.Column(db.String(100))  # Font Awesome icon class
    
    # Room settings
    is_public = db.Column(db.Boolean, default=True)
    requires_approval = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', back_populates='room', lazy='dynamic')
    members = db.relationship('RoomMembership', back_populates='room', lazy='dynamic')
    
    def member_count(self):
        return self.members.filter_by(is_active=True).count()
    
    def post_count(self):
        return self.posts.count()
    
    def is_member(self, user):
        return self.members.filter_by(user_id=user.id, is_active=True).first() is not None


class RoomMembership(db.Model):
    """Track user membership in investment rooms"""
    __tablename__ = 'room_memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('investment_rooms.id'), nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    is_moderator = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='room_memberships')
    room = db.relationship('InvestmentRoom', back_populates='members')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'room_id', name='unique_room_membership'),)


class Achievement(db.Model):
    """Achievement badges that users can earn"""
    __tablename__ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(100))  # Font Awesome icon or emoji
    category = db.Column(db.String(50))  # 'learning', 'community', 'investing', 'milestone'
    
    # Points awarded for this achievement
    points = db.Column(db.Integer, default=10)
    
    # Requirements (stored as JSON string)
    # Example: {"modules_completed": 10} or {"posts_created": 5}
    requirements = db.Column(db.Text)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user_achievements = db.relationship('UserAchievement', back_populates='achievement', lazy='dynamic')


class UserAchievement(db.Model):
    """Track which achievements users have earned"""
    __tablename__ = 'user_achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='achievements')
    achievement = db.relationship('Achievement', back_populates='user_achievements')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),)


class TrendingTopic(db.Model):
    """Track trending hashtags and topics"""
    __tablename__ = 'trending_topics'
    
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(100), nullable=False, unique=True)
    
    # Metrics
    mention_count = db.Column(db.Integer, default=0)
    post_count = db.Column(db.Integer, default=0)
    unique_users = db.Column(db.Integer, default=0)
    
    # Trend score (calculated: mentions * recency factor)
    trend_score = db.Column(db.Float, default=0.0)
    
    # Time tracking
    last_mentioned = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def update_trending(tags_list, user_id):
        """Update trending topics from a list of tags"""
        from datetime import datetime, timedelta
        
        for tag in tags_list:
            tag = tag.strip().lower()
            if not tag:
                continue
                
            topic = TrendingTopic.query.filter_by(tag=tag).first()
            if not topic:
                topic = TrendingTopic(tag=tag)
                db.session.add(topic)
            
            topic.mention_count += 1
            topic.post_count += 1
            topic.last_mentioned = datetime.utcnow()
            
            # Calculate trend score (recent mentions weighted higher)
            hours_since_update = (datetime.utcnow() - topic.created_at).total_seconds() / 3600
            recency_factor = 1.0 / (1.0 + hours_since_update / 24.0)  # Decay over days
            topic.trend_score = topic.mention_count * recency_factor
        
        db.session.commit()
    
    @staticmethod
    def get_trending(limit=10):
        """Get top trending topics"""
        return TrendingTopic.query.order_by(
            TrendingTopic.trend_score.desc()
        ).limit(limit).all()


class NewsletterSubscription(db.Model):
    """Track newsletter subscriptions"""
    __tablename__ = 'newsletter_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Subscription preferences
    weekly_digest = db.Column(db.Boolean, default=True)
    trending_topics = db.Column(db.Boolean, default=True)
    investment_opportunities = db.Column(db.Boolean, default=True)
    specialty_updates = db.Column(db.Boolean, default=True)
    
    is_active = db.Column(db.Boolean, default=True)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    unsubscribed_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref='newsletter_subscription')
    
    __table_args__ = (db.UniqueConstraint('user_id', name='unique_newsletter_subscription'),)
