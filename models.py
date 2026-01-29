from datetime import datetime, timedelta
from enum import Enum
import string
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from sqlalchemy import UniqueConstraint
from app import db
import pyotp


# =============================================================================
# ENUMS
# =============================================================================

class SubscriptionTier(Enum):
    FREE = 'free'
    PRO = 'pro'
    ELITE = 'elite'
    PREMIUM = 'premium'  # Legacy alias for pro

class DealStatus(Enum):
    DRAFT = 'draft'
    REVIEW = 'review'
    ACTIVE = 'active'
    CLOSED = 'closed'
    REJECTED = 'rejected'

class AMAStatus(Enum):
    SCHEDULED = 'scheduled'
    LIVE = 'live'
    ENDED = 'ended'
    CANCELLED = 'cancelled'

class MentorshipStatus(Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    COMPLETED = 'completed'


class NotificationType(Enum):
    MENTION = 'mention'
    LIKE = 'like'
    COMMENT = 'comment'
    FOLLOW = 'follow'
    REPLY = 'reply'
    AMA_REMINDER = 'ama_reminder'
    AMA_ANSWER = 'ama_answer'
    DEAL_ALERT = 'deal_alert'
    MENTORSHIP_REQUEST = 'mentorship_request'
    MENTORSHIP_ACCEPTED = 'mentorship_accepted'
    REFERRAL_SIGNUP = 'referral_signup'
    INVITE_ACCEPTED = 'invite_accepted'
    LEVEL_UP = 'level_up'
    SYSTEM = 'system'
    CONNECTION_REQUEST = 'connection_request'
    CONNECTION_ACCEPTED = 'connection_accepted'


# =============================================================================
# MODELS
# =============================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    replit_id = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    medical_license = db.Column(db.String(50), unique=True, nullable=True)
    specialty = db.Column(db.String(100), nullable=True)
    # Trust & verification
    npi_number = db.Column(db.String(20), unique=True)
    npi_verified = db.Column(db.Boolean, default=False)
    license_state = db.Column(db.String(2))
    role = db.Column(db.String(30), default='physician')  # physician, resident, fellow, attending, sponsor, admin
    verification_status = db.Column(db.String(30), default='unverified')  # unverified, pending, verified, rejected
    verification_submitted_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)
    verification_notes = db.Column(db.Text)

    hospital_affiliation = db.Column(db.String(200))
    bio = db.Column(db.Text)
    profile_image_url = db.Column(db.String(500))
    location = db.Column(db.String(100))
    years_of_experience = db.Column(db.Integer)
    investment_interests = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    account_active = db.Column(db.Boolean, default=True)
    is_profile_public = db.Column(db.Boolean, default=True)
    # Reputation score (cached). Always derived from ReputationEvent stream.
    reputation_score = db.Column(db.Integer, default=0)
    # Invite-only growth
    invite_credits = db.Column(db.Integer, default=2)
    invite_id = db.Column(db.Integer, db.ForeignKey('invites.id'))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    # Admin permissions
    can_review_verifications = db.Column(db.Boolean, default=False)
    # Stripe integration
    stripe_customer_id = db.Column(db.String(100), unique=True, nullable=True)
    # Subscription & gamification
    subscription_tier = db.Column(db.String(20), default='free')
    subscription_ends_at = db.Column(db.DateTime)
    premium_permanent = db.Column(db.Boolean, default=False)
    premium_granted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    premium_granted_at = db.Column(db.DateTime)
    premium_grant_reason = db.Column(db.String(255))
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    login_streak = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(10), unique=True)
    custom_role_id = db.Column(db.Integer, db.ForeignKey('custom_roles.id'))
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Two-Factor Authentication fields
    totp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    
    # Password reset fields
    password_reset_token = db.Column(db.String(100))
    password_reset_expires = db.Column(db.DateTime)
    
    # Social login IDs
    facebook_id = db.Column(db.String(50), unique=True, nullable=True)
    google_id = db.Column(db.String(50), unique=True, nullable=True)
    apple_id = db.Column(db.String(100), unique=True, nullable=True)
    github_id = db.Column(db.String(50), unique=True, nullable=True)
    
    # Physician verification fields
    professional_email = db.Column(db.String(120))
    professional_email_verified = db.Column(db.Boolean, default=False)
    professional_email_code = db.Column(db.String(6))
    professional_email_code_expires = db.Column(db.DateTime)
    license_document_url = db.Column(db.String(500))
    license_document_uploaded_at = db.Column(db.DateTime)
    license_verified = db.Column(db.Boolean, default=False)
    
    # Moderation fields
    warning_count = db.Column(db.Integer, default=0)
    is_banned = db.Column(db.Boolean, default=False)
    banned_at = db.Column(db.DateTime)
    ban_reason = db.Column(db.String(500))
    
    # Relationships
    progress = db.relationship('UserProgress', back_populates='user', lazy='dynamic')
    forum_posts = db.relationship('ForumPost', back_populates='author', lazy='dynamic')
    transactions = db.relationship('PortfolioTransaction', back_populates='user', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    likes = db.relationship('Like', back_populates='user', lazy='dynamic')
    # Group and messaging relationships
    group_memberships = db.relationship('GroupMembership', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    sent_connections = db.relationship('Connection', foreign_keys='Connection.requester_id', backref=db.backref('requester', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    received_connections = db.relationship('Connection', foreign_keys='Connection.addressee_id', backref=db.backref('addressee', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    dm_participations = db.relationship('DirectMessageParticipant', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    reputation_events = db.relationship('ReputationEvent', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    invites_sent = db.relationship('Invite', back_populates='inviter', lazy='dynamic', foreign_keys='Invite.inviter_user_id')
    invite = db.relationship('Invite', foreign_keys=[invite_id])
    
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
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret
    
    def get_totp_uri(self):
        if not self.totp_secret:
            return None
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name="MedLearn Invest"
        )
    
    def verify_totp(self, token):
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)
    
    def generate_password_reset_token(self):
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        return self.password_reset_token
    
    def verify_reset_token(self, token):
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        if datetime.utcnow() > self.password_reset_expires:
            return False
        return secrets.compare_digest(self.password_reset_token, token)
    
    def clear_reset_token(self):
        self.password_reset_token = None
        self.password_reset_expires = None
    
    def generate_referral_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            existing = User.query.filter_by(referral_code=code).first()
            if not existing:
                self.referral_code = code
                break
    
    @property
    def is_premium(self):
        if self.premium_permanent:
            return True
        if self.subscription_tier == 'premium':
            if self.subscription_ends_at is None or self.subscription_ends_at > datetime.utcnow():
                return True
        return False
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    def add_points(self, amount):
        """Add points and update level (1 level per 500 points)"""
        if self.points is None:
            self.points = 0
        self.points += amount
        self.level = (self.points // 500) + 1
    
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
        # Get posts from followed users
        following_ids = [f.following_id for f in self.following.all()]
        following_ids.append(self.id)  # Include own posts
        return Post.query.filter(Post.author_id.in_(following_ids)).order_by(Post.created_at.desc())


class Module(db.Model):
    __tablename__ = 'modules'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)  # Beginner, Intermediate, Advanced
    estimated_duration = db.Column(db.Integer)  # in minutes
    category = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    progress = db.relationship('UserProgress', back_populates='module', lazy='dynamic')


class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completion_date = db.Column(db.DateTime)
    time_spent = db.Column(db.Integer, default=0)  # in minutes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
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
    
    # Relationships
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
    
    # Relationships
    topic = db.relationship('ForumTopic', back_populates='posts')
    author = db.relationship('User', back_populates='forum_posts')
    replies = db.relationship('ForumPost', backref='parent', remote_side=[id])


class PortfolioTransaction(db.Model):
    __tablename__ = 'portfolio_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # BUY, SELL
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='transactions')


class Resource(db.Model):
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    resource_type = db.Column(db.String(50), nullable=False)  # Calculator, Guide, Tool, etc.
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# OAuth Model for Replit Auth
class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = 'flask_dance_oauth'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    browser_session_key = db.Column(db.String(100), nullable=False)
    user = db.relationship('User')
    
    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_provider',
    ),)


# Social Media Models
class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    room_id = db.Column(db.Integer, db.ForeignKey('investment_rooms.id'))
    visibility = db.Column(db.String(20), default='physicians')  # public, physicians, group
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    post_type = db.Column(db.String(20), default='general')  # general, question, insight, achievement, deal
    tags = db.Column(db.String(500))  # Comma-separated tags
    is_published = db.Column(db.Boolean, default=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    anonymous_name = db.Column(db.String(50))  # e.g., "Anonymous Cardiologist"
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    share_count = db.Column(db.Integer, default=0)
    media_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    facebook_post_id = db.Column(db.String(100), unique=True, nullable=True)  # For FB sync deduplication
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', back_populates='posts')
    group = db.relationship('Group', back_populates='posts')
    comments = db.relationship('Comment', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    media = db.relationship('PostMedia', back_populates='post', lazy='dynamic', order_by='PostMedia.order_index', cascade='all, delete-orphan')
    
    @property
    def user_id(self):
        """Alias for author_id for blueprint compatibility"""
        return self.author_id
    
    @property
    def score(self):
        return self.upvotes - self.downvotes
    
    @property
    def display_author(self):
        if self.is_anonymous:
            return self.anonymous_name or "Anonymous"
        return self.author.full_name
    
    def likes_count(self):
        return self.likes.count()
    
    def comments_count(self):
        return self.comments.count()
    
    def is_liked_by(self, user):
        return self.likes.filter_by(user_id=user.id).first() is not None
    
    def get_display_name(self):
        """Get display name, showing specialty/location for anonymous posts"""
        if self.is_anonymous:
            specialty = self.author.specialty or 'Physician'
            location = self.author.location or 'USA'
            return f"{specialty} • {location}"
        return self.author.full_name
    
    @property
    def has_media(self):
        return self.media_count > 0
    
    @property
    def first_media(self):
        return self.media.first()
    
    @property
    def all_media(self):
        return self.media.order_by(PostMedia.order_index).all()


class PostMedia(db.Model):
    """Media attachments for posts (images and videos)"""
    __tablename__ = 'post_media'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    media_type = db.Column(db.String(20), nullable=False)  # 'image' or 'video'
    file_path = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255))
    
    thumbnail_path = db.Column(db.String(500))
    video_thumbnail = db.Column(db.String(500))
    duration_seconds = db.Column(db.Integer)  # Max 60 seconds for short videos
    
    file_size = db.Column(db.Integer)  # In bytes
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    
    order_index = db.Column(db.Integer, default=0)  # For carousel ordering
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', back_populates='media')


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    post = db.relationship('Post', back_populates='comments')
    author = db.relationship('User', back_populates='comments')
    replies = db.relationship('Comment', backref='parent', remote_side=[id])


class Like(db.Model):
    __tablename__ = 'likes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='likes')
    post = db.relationship('Post', back_populates='likes')
    
    # Ensure a user can only like a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)


class Follow(db.Model):
    __tablename__ = 'follows'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ensure a user can't follow the same person twice
    __table_args__ = (db.UniqueConstraint('follower_id', 'following_id', name='unique_follow_relationship'),)


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    url = db.Column(db.String(500))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    actor = db.relationship('User', foreign_keys=[actor_id])
    post = db.relationship('Post')


# Invite-only growth

class Invite(db.Model):
    __tablename__ = 'invites'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    invitee_email = db.Column(db.String(255))
    status = db.Column(db.String(20), default='issued', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    accepted_at = db.Column(db.DateTime)

    inviter = db.relationship('User', back_populates='invites_sent', foreign_keys=[inviter_user_id])

    @staticmethod
    def new_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))


# Weekly Digest (retention)

class Digest(db.Model):
    __tablename__ = 'digests'

    id = db.Column(db.Integer, primary_key=True)
    period_start = db.Column(db.DateTime, nullable=False, index=True)
    period_end = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    items = db.relationship('DigestItem', back_populates='digest', lazy='dynamic')


class DigestItem(db.Model):
    __tablename__ = 'digest_items'

    id = db.Column(db.Integer, primary_key=True)
    digest_id = db.Column(db.Integer, db.ForeignKey('digests.id'), nullable=False, index=True)
    item_type = db.Column(db.String(20), nullable=False, index=True)
    entity_id = db.Column(db.Integer)
    score = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer)
    payload_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    digest = db.relationship('Digest', back_populates='items')


# Community models (Groups, Connections, Messaging, Reputation)

class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    privacy = db.Column(db.String(20), default='private')  # public, private, hidden
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by_id])
    memberships = db.relationship('GroupMembership', back_populates='group', lazy='dynamic', cascade='all, delete-orphan')
    posts = db.relationship('Post', back_populates='group', lazy='dynamic')


class GroupMembership(db.Model):
    __tablename__ = 'group_memberships'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # member, moderator, admin
    status = db.Column(db.String(20), default='active')  # active, pending, banned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship('Group', back_populates='memberships')
    user = db.relationship('User', back_populates='group_memberships')

    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_membership'),)


class Connection(db.Model):
    __tablename__ = 'connections'

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    __table_args__ = (db.UniqueConstraint('requester_id', 'addressee_id', name='unique_connection_request'),)


class DirectMessageThread(db.Model):
    __tablename__ = 'dm_threads'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    participants = db.relationship('DirectMessageParticipant', back_populates='thread', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('DirectMessage', back_populates='thread', lazy='dynamic', cascade='all, delete-orphan')


class DirectMessageParticipant(db.Model):
    __tablename__ = 'dm_participants'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('dm_threads.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    thread = db.relationship('DirectMessageThread', back_populates='participants')
    user = db.relationship('User', back_populates='dm_participations')

    __table_args__ = (db.UniqueConstraint('thread_id', 'user_id', name='unique_dm_participant'),)


class DirectMessage(db.Model):
    __tablename__ = 'dm_messages'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('dm_threads.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    thread = db.relationship('DirectMessageThread', back_populates='messages')
    sender = db.relationship('User', foreign_keys=[sender_id])


class ReputationEvent(db.Model):
    __tablename__ = 'reputation_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # post_upvote, comment_upvote, accepted_answer, moderation_action
    weight = db.Column(db.Integer, default=1)
    related_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    related_group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    meta_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='reputation_events')
    related_post = db.relationship('Post')
    related_group = db.relationship('Group')


# Deal-first investing schema (extends Post)

class DealDetails(db.Model):
    """One-to-one extension for Post when post_type == 'deal'."""

    __tablename__ = 'deal_details'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, unique=True)

    # Core fields (structured)
    asset_class = db.Column(db.String(60), nullable=False)  # e.g., self-storage, multifamily, PE, VC, crypto
    strategy = db.Column(db.String(60))  # value-add, core, development, arbitrage, etc.
    location = db.Column(db.String(120))
    time_horizon_months = db.Column(db.Integer)
    target_irr = db.Column(db.Float)
    target_multiple = db.Column(db.Float)
    minimum_investment = db.Column(db.Integer)

    sponsor_name = db.Column(db.String(120))
    sponsor_track_record = db.Column(db.Text)
    thesis = db.Column(db.Text, nullable=False)
    key_risks = db.Column(db.Text)
    diligence_needed = db.Column(db.Text)
    feedback_areas = db.Column(db.String(200))
    disclaimer_acknowledged = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), default='open')  # open, closed, pass

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = db.relationship('Post')
    analyses = db.relationship('DealAnalysis', back_populates='deal', lazy='dynamic', cascade='all, delete-orphan')


class DealAnalysis(db.Model):
    __tablename__ = 'deal_analyses'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal_details.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    provider = db.Column(db.String(40), default='openai')
    model = db.Column(db.String(80))
    output_text = db.Column(db.Text, nullable=False)
    output_json = db.Column(db.Text)  # optional structured json
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    deal = db.relationship('DealDetails', back_populates='analyses')
    created_by = db.relationship('User', foreign_keys=[created_by_id])


class AiJob(db.Model):
    """DB-backed job queue for AI tasks.

    Run a worker process (worker.py) to execute pending jobs.
    """

    __tablename__ = 'ai_jobs'

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(40), nullable=False)  # summarize_thread, analyze_deal
    status = db.Column(db.String(20), default='queued')  # queued, running, done, failed

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deal_details.id'))
    input_text = db.Column(db.Text)

    idempotency_key = db.Column(db.String(120))
    request_fingerprint = db.Column(db.String(64), index=True)

    output_text = db.Column(db.Text)
    output_json = db.Column(db.Text)
    error = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    post = db.relationship('Post', foreign_keys=[post_id])
    deal = db.relationship('DealDetails', foreign_keys=[deal_id])


class UserActivity(db.Model):
    """Lightweight activity log for accurate WAU/DAU and cohort analytics."""
    __tablename__ = 'user_activity'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    activity_type = db.Column(db.String(30), nullable=False)  # view, post, comment, endorse, deal_create, ai_run, invite_accept
    entity_type = db.Column(db.String(30))  # deal, post, comment, digest, invite
    entity_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id])


class NotificationPreference(db.Model):
    """User notification preferences for different channels"""
    __tablename__ = 'notification_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # In-app notifications
    in_app_likes = db.Column(db.Boolean, default=True)
    in_app_comments = db.Column(db.Boolean, default=True)
    in_app_follows = db.Column(db.Boolean, default=True)
    in_app_mentions = db.Column(db.Boolean, default=True)
    in_app_deals = db.Column(db.Boolean, default=True)
    in_app_amas = db.Column(db.Boolean, default=True)
    in_app_messages = db.Column(db.Boolean, default=True)
    
    # Email notifications
    email_digest = db.Column(db.String(20), default='weekly')  # none, daily, weekly
    email_deals = db.Column(db.Boolean, default=True)
    email_events = db.Column(db.Boolean, default=True)
    email_newsletter = db.Column(db.Boolean, default=True)
    email_marketing = db.Column(db.Boolean, default=False)
    
    # Push notifications
    push_enabled = db.Column(db.Boolean, default=True)
    push_likes = db.Column(db.Boolean, default=False)
    push_comments = db.Column(db.Boolean, default=True)
    push_messages = db.Column(db.Boolean, default=True)
    push_deals = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('notification_preferences', uselist=False))


class Alert(db.Model):
    """Operational alerts for SLA breaches and other metrics."""
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)  # verification_sla
    metric = db.Column(db.String(30), nullable=False)  # p50, p95
    value_hours = db.Column(db.Float, nullable=False)
    threshold_hours = db.Column(db.Float, nullable=False)
    window_start = db.Column(db.DateTime, nullable=False)
    window_end = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# SUBSCRIPTION & PAYMENTS
# ============================================================================

class Subscription(db.Model):
    """Track subscription history and payments"""
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tier = db.Column(db.String(20), nullable=False)  # free, premium, enterprise
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    stripe_price_id = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    interval = db.Column(db.String(20))  # month or year
    status = db.Column(db.String(20))  # active, cancelled, past_due
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='subscriptions')


class Payment(db.Model):
    """Track individual payments"""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20))  # succeeded, pending, failed
    payment_type = db.Column(db.String(50))  # subscription, course, event
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='payments')


# ============================================================================
# EXPERT AMAs
# ============================================================================

class ExpertAMA(db.Model):
    """Scheduled Q&A sessions with experts"""
    __tablename__ = 'expert_amas'

    id = db.Column(db.Integer, primary_key=True)
    expert_name = db.Column(db.String(200), nullable=False)
    expert_title = db.Column(db.String(200))
    expert_bio = db.Column(db.Text)
    expert_image_url = db.Column(db.String(500))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    topic_tags = db.Column(db.String(500))
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, live, ended, cancelled
    is_premium_only = db.Column(db.Boolean, default=False)
    max_participants = db.Column(db.Integer)
    sponsor_name = db.Column(db.String(200))
    sponsor_logo_url = db.Column(db.String(500))
    sponsor_url = db.Column(db.String(500))
    recording_url = db.Column(db.String(500))
    recording_price = db.Column(db.Float)
    youtube_live_url = db.Column(db.String(500))
    session_type = db.Column(db.String(50), default='ama')  # ama, talk, pitch, education, webinar
    ticket_price = db.Column(db.Float)
    participant_count = db.Column(db.Integer, default=0)
    question_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship('AMAQuestion', back_populates='ama', lazy='dynamic')
    registrations = db.relationship('AMARegistration', back_populates='ama', lazy='dynamic')


class AMAQuestion(db.Model):
    """Questions asked during AMA"""
    __tablename__ = 'ama_questions'

    id = db.Column(db.Integer, primary_key=True)
    ama_id = db.Column(db.Integer, db.ForeignKey('expert_amas.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    upvotes = db.Column(db.Integer, default=0)
    answer = db.Column(db.Text)
    answered_at = db.Column(db.DateTime)
    is_answered = db.Column(db.Boolean, default=False)
    asked_at = db.Column(db.DateTime, default=datetime.utcnow)

    ama = db.relationship('ExpertAMA', back_populates='questions')
    user = db.relationship('User', backref='ama_questions')


class AMARegistration(db.Model):
    """Track who registered for AMAs"""
    __tablename__ = 'ama_registrations'

    id = db.Column(db.Integer, primary_key=True)
    ama_id = db.Column(db.Integer, db.ForeignKey('expert_amas.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attended = db.Column(db.Boolean, default=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    ama = db.relationship('ExpertAMA', back_populates='registrations')
    user = db.relationship('User', backref='ama_registrations')

    __table_args__ = (db.UniqueConstraint('ama_id', 'user_id', name='unique_ama_registration'),)


# ============================================================================
# INVESTMENT DEAL MARKETPLACE
# ============================================================================

class InvestmentDeal(db.Model):
    """Investment opportunities for physicians"""
    __tablename__ = 'investment_deals'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deal_type = db.Column(db.String(50), nullable=False)  # real_estate, fund, practice, syndicate
    minimum_investment = db.Column(db.Float, nullable=False)
    target_raise = db.Column(db.Float)
    current_raised = db.Column(db.Float, default=0)
    projected_return = db.Column(db.String(50))
    investment_term = db.Column(db.String(50))
    accredited_only = db.Column(db.Boolean, default=True)
    physician_only = db.Column(db.Boolean, default=False)
    sponsor_name = db.Column(db.String(200), nullable=False)
    sponsor_bio = db.Column(db.Text)
    sponsor_track_record = db.Column(db.Text)
    sponsor_contact = db.Column(db.String(200))
    location = db.Column(db.String(200))
    offering_document_url = db.Column(db.String(500))
    pitch_deck_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='draft')  # draft, review, active, closed, rejected
    deadline = db.Column(db.DateTime)
    is_featured = db.Column(db.Boolean, default=False)
    featured_until = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0)
    interest_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interests = db.relationship('DealInterest', back_populates='deal', lazy='dynamic')


class DealInterest(db.Model):
    """Track user interest in deals"""
    __tablename__ = 'deal_interests'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('investment_deals.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    investment_amount = db.Column(db.Float)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='interested')  # interested, contacted, invested
    contacted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    deal = db.relationship('InvestmentDeal', back_populates='interests')
    user = db.relationship('User', backref='deal_interests')

    __table_args__ = (db.UniqueConstraint('deal_id', 'user_id', name='unique_deal_interest'),)


# ============================================================================
# MENTORSHIP
# ============================================================================

class Mentorship(db.Model):
    """Mentor-mentee relationships"""
    __tablename__ = 'mentorships'

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    focus_areas = db.Column(db.String(500))
    duration_months = db.Column(db.Integer, default=3)
    status = db.Column(db.String(20), default='pending')  # pending, active, completed, cancelled
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    total_meetings = db.Column(db.Integer, default=0)
    last_meeting = db.Column(db.DateTime)
    mentor_rating = db.Column(db.Integer)
    mentee_rating = db.Column(db.Integer)
    mentor_feedback = db.Column(db.Text)
    mentee_feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mentor = db.relationship('User', foreign_keys=[mentor_id], backref='mentorships_as_mentor')
    mentee = db.relationship('User', foreign_keys=[mentee_id], backref='mentorships_as_mentee')
    sessions = db.relationship('MentorshipSession', back_populates='mentorship', lazy='dynamic')


class MentorshipSession(db.Model):
    """Individual mentorship meetings"""
    __tablename__ = 'mentorship_sessions'

    id = db.Column(db.Integer, primary_key=True)
    mentorship_id = db.Column(db.Integer, db.ForeignKey('mentorships.id'), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    topics_discussed = db.Column(db.Text)
    action_items = db.Column(db.Text)
    notes = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mentorship = db.relationship('Mentorship', back_populates='sessions')


class MentorApplication(db.Model):
    """Applications to become a mentor"""
    __tablename__ = 'mentor_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    specialty_areas = db.Column(db.String(500))  # Investment topics they can mentor on
    years_investing = db.Column(db.Integer)
    investment_experience = db.Column(db.Text)  # Description of their investing experience
    mentoring_experience = db.Column(db.Text)  # Prior mentoring experience
    motivation = db.Column(db.Text)  # Why they want to be a mentor
    availability = db.Column(db.String(200))  # Hours per month available
    linkedin_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='mentor_applications')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])


# ============================================================================
# LTI 1.3 INTEGRATION
# ============================================================================

class LTITool(db.Model):
    """LTI 1.3 Tool configuration for external learning platforms"""
    __tablename__ = 'lti_tools'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # LTI 1.3 Configuration
    issuer = db.Column(db.String(500), nullable=False)  # Tool's issuer/platform ID
    client_id = db.Column(db.String(200), nullable=False)  # Our client ID registered with the tool
    deployment_id = db.Column(db.String(200))  # Deployment ID
    
    # Tool Endpoints
    oidc_auth_url = db.Column(db.String(500), nullable=False)  # OIDC authorization URL
    token_url = db.Column(db.String(500))  # Token endpoint for API calls
    jwks_url = db.Column(db.String(500), nullable=False)  # Tool's JWKS endpoint
    launch_url = db.Column(db.String(500), nullable=False)  # Tool launch/target link URL
    
    # Our Platform Keys (generated)
    public_key = db.Column(db.Text)  # Our platform's public key (PEM)
    private_key = db.Column(db.Text)  # Our platform's private key (PEM)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    courses = db.relationship('Course', backref='lti_tool', lazy='dynamic')


# ============================================================================
# COURSES & EDUCATIONAL CONTENT
# ============================================================================

class Course(db.Model):
    """Premium courses"""
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instructor_name = db.Column(db.String(200))
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    total_modules = db.Column(db.Integer, default=0)
    total_duration_minutes = db.Column(db.Integer, default=0)
    difficulty_level = db.Column(db.String(20))
    thumbnail_url = db.Column(db.String(500))
    preview_video_url = db.Column(db.String(500))
    course_url = db.Column(db.String(500))
    course_embed_code = db.Column(db.Text)  # Iframe or embed code for external courses
    lti_tool_id = db.Column(db.Integer, db.ForeignKey('lti_tools.id'))  # LTI tool for this course
    lti_resource_link_id = db.Column(db.String(200))  # Unique ID for this course in LTI context
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    enrolled_count = db.Column(db.Integer, default=0)
    completion_rate = db.Column(db.Float, default=0)
    avg_rating = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    modules = db.relationship('CourseModule', back_populates='course', lazy='dynamic')
    enrollments = db.relationship('CourseEnrollment', back_populates='course', lazy='dynamic')


class CourseModule(db.Model):
    """Course content modules"""
    __tablename__ = 'course_modules'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    video_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    order_index = db.Column(db.Integer, default=0)
    downloadable_resources = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', back_populates='modules')


class CourseEnrollment(db.Model):
    """Track course purchases and progress"""
    __tablename__ = 'course_enrollments'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    progress_percent = db.Column(db.Float, default=0)
    completed_modules = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    rating = db.Column(db.Integer)
    review = db.Column(db.Text)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', back_populates='enrollments')
    user = db.relationship('User', backref='course_enrollments')

    __table_args__ = (db.UniqueConstraint('course_id', 'user_id', name='unique_course_enrollment'),)


# ============================================================================
# EVENTS & CONFERENCES
# ============================================================================

class Event(db.Model):
    """Virtual conferences and events"""
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_type = db.Column(db.String(50))  # conference, workshop, networking
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    timezone = db.Column(db.String(50), default='America/New_York')
    is_virtual = db.Column(db.Boolean, default=True)
    venue_name = db.Column(db.String(200))
    venue_address = db.Column(db.Text)
    meeting_url = db.Column(db.String(500))
    meeting_password = db.Column(db.String(100))
    early_bird_price = db.Column(db.Float)
    early_bird_ends = db.Column(db.DateTime)
    regular_price = db.Column(db.Float, nullable=False)
    vip_price = db.Column(db.Float)
    max_attendees = db.Column(db.Integer)
    current_attendees = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    banner_url = db.Column(db.String(500))
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approval_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    registrations = db.relationship('EventRegistration', back_populates='event', lazy='dynamic')
    sessions = db.relationship('EventSession', back_populates='event', lazy='dynamic')


class EventSession(db.Model):
    """Individual sessions within an event"""
    __tablename__ = 'event_sessions'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    speaker_name = db.Column(db.String(200))
    speaker_bio = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    recording_url = db.Column(db.String(500))

    event = db.relationship('Event', back_populates='sessions')


class EventRegistration(db.Model):
    """Event ticket purchases"""
    __tablename__ = 'event_registrations'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticket_type = db.Column(db.String(20))  # regular, vip
    purchase_price = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    attended = db.Column(db.Boolean, default=False)
    check_in_time = db.Column(db.DateTime)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship('Event', back_populates='registrations')
    user = db.relationship('User', backref='event_registrations')

    __table_args__ = (db.UniqueConstraint('event_id', 'user_id', name='unique_event_registration'),)


# ============================================================================
# REFERRAL PROGRAM
# ============================================================================

class Referral(db.Model):
    """Track referrals and rewards"""
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    referral_code_used = db.Column(db.String(20))
    status = db.Column(db.String(20), default='pending')  # pending, completed, rewarded
    reward_type = db.Column(db.String(50))  # points, premium_month, cash
    reward_value = db.Column(db.Float)
    rewarded_at = db.Column(db.DateTime)
    referred_user_activated = db.Column(db.Boolean, default=False)
    referred_user_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_sent')
    referred_user = db.relationship('User', foreign_keys=[referred_user_id], backref='referral_received')


# ============================================================================
# EMAIL CAMPAIGNS
# ============================================================================

class EmailCampaign(db.Model):
    """Email marketing campaigns"""
    __tablename__ = 'email_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    text_content = db.Column(db.Text)
    segment = db.Column(db.String(100))  # all, free, premium, specialty_cardiology
    send_at = db.Column(db.DateTime)
    sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    total_recipients = db.Column(db.Integer, default=0)
    opened = db.Column(db.Integer, default=0)
    clicked = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# VERIFICATION QUEUE & SLA TRACKING
# ============================================================================

class VerificationQueueEntry(db.Model):
    """Track verification requests with SLA and assignment"""
    __tablename__ = 'verification_queue_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sla_deadline = db.Column(db.DateTime)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, in_review, approved, rejected
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)

    user = db.relationship('User', foreign_keys=[user_id], backref='verification_queue_entry')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])


# ============================================================================
# ONBOARDING PROMPTS
# ============================================================================

class OnboardingPrompt(db.Model):
    """Cohort-specific onboarding prompts"""
    __tablename__ = 'onboarding_prompts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_url = db.Column(db.String(300))
    action_label = db.Column(db.String(100))
    target_cohort = db.Column(db.String(50))  # all, new_user, specialty_cardiology, etc.
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserPromptDismissal(db.Model):
    """Track which prompts users have dismissed"""
    __tablename__ = 'user_prompt_dismissals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey('onboarding_prompts.id'), nullable=False)
    dismissed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='prompt_dismissals')
    prompt = db.relationship('OnboardingPrompt')

    __table_args__ = (db.UniqueConstraint('user_id', 'prompt_id', name='unique_user_prompt_dismissal'),)


# ============================================================================
# INVITE CREDITS & BOOSTS
# ============================================================================

class InviteCreditEvent(db.Model):
    """Track invite credit changes"""
    __tablename__ = 'invite_credit_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    delta = db.Column(db.Integer, nullable=False)  # positive = credits added, negative = used
    reason = db.Column(db.String(100), nullable=False)  # signup_bonus, specialty_boost, invite_used, admin_grant
    related_invite_id = db.Column(db.Integer, db.ForeignKey('invites.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='invite_credit_events')
    related_invite = db.relationship('Invite')


# ============================================================================
# COHORT NORMS & MODERATION
# ============================================================================

class CohortNorm(db.Model):
    """Thresholds for auto-moderation by cohort"""
    __tablename__ = 'cohort_norms'

    id = db.Column(db.Integer, primary_key=True)
    cohort = db.Column(db.String(50), nullable=False, unique=True)  # global, specialty_cardiology, etc.
    min_reputation_to_post = db.Column(db.Integer, default=-10)
    auto_hide_threshold = db.Column(db.Integer, default=3)  # hide after N reports
    auto_lock_threshold = db.Column(db.Integer, default=5)  # lock after N reports
    downrank_after_reports = db.Column(db.Integer, default=2)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModerationEvent(db.Model):
    """Audit log for moderation actions"""
    __tablename__ = 'moderation_events'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False)  # post, comment, user
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(30), nullable=False)  # hide, lock, downrank, unhide, unlock
    reason = db.Column(db.String(100))  # auto_reports, admin_action, spam_detected
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_automated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    performed_by = db.relationship('User')


class ContentReport(db.Model):
    """User-submitted content reports"""
    __tablename__ = 'content_reports'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    entity_type = db.Column(db.String(30), nullable=False)  # post, comment, user
    entity_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)  # spam, harassment, misinformation, other
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open, resolved, dismissed
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolution = db.Column(db.String(50))  # no_action, hide, lock, warning
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reports_submitted')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])

    __table_args__ = (db.UniqueConstraint('reporter_id', 'entity_type', 'entity_id', name='unique_report_per_user'),)
    
    def to_dict(self, include_content=False):
        """Convert report to dictionary for API responses"""
        data = {
            'id': self.id,
            'reporter_id': self.reporter_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'reason': self.reason,
            'details': self.details,
            'status': self.status,
            'resolved_by_id': self.resolved_by_id,
            'resolution': self.resolution,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_content:
            data['reporter'] = {
                'id': self.reporter.id,
                'name': self.reporter.full_name,
                'email': self.reporter.email
            } if self.reporter else None
            
            data['resolved_by'] = {
                'id': self.resolved_by.id,
                'name': self.resolved_by.full_name
            } if self.resolved_by else None
            
            if self.entity_type == 'post':
                from models import Post
                post = Post.query.get(self.entity_id)
                if post:
                    data['content'] = {
                        'type': 'post',
                        'content': post.content[:500] if post.content else None,
                        'author_id': post.author_id,
                        'created_at': post.created_at.isoformat() if post.created_at else None
                    }
            elif self.entity_type == 'comment':
                from models import Comment
                comment = Comment.query.get(self.entity_id)
                if comment:
                    data['content'] = {
                        'type': 'comment',
                        'content': comment.content[:500] if comment.content else None,
                        'author_id': comment.author_id,
                        'created_at': comment.created_at.isoformat() if comment.created_at else None
                    }
            elif self.entity_type == 'user':
                reported_user = User.query.get(self.entity_id)
                if reported_user:
                    data['content'] = {
                        'type': 'user',
                        'name': reported_user.full_name,
                        'email': reported_user.email
                    }
        
        return data


# ============================================================================
# DEAL OUTCOMES
class BugReport(db.Model):
    """User-submitted bug/error reports for platform issues"""
    __tablename__ = 'bug_reports'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # bug, error, suggestion, other
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    page_url = db.Column(db.String(500))  # Where the error occurred
    browser_info = db.Column(db.String(200))
    screenshot_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    admin_notes = db.Column(db.Text)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='bug_reports')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])


# ============================================================================

class DealOutcome(db.Model):
    """Track deal outcomes and lessons learned"""
    __tablename__ = 'deal_outcomes'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('investment_deals.id'), nullable=False, unique=True)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    outcome_status = db.Column(db.String(30), nullable=False)  # closed_success, closed_loss, passed, ongoing
    actual_return = db.Column(db.String(50))
    actual_term = db.Column(db.String(50))
    lessons_learned = db.Column(db.Text)
    would_invest_again = db.Column(db.Boolean)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deal = db.relationship('InvestmentDeal', backref='outcome')
    submitted_by = db.relationship('User', backref='deal_outcomes_submitted')


# ============================================================================
# SPONSOR VETTING
# ============================================================================

class SponsorProfile(db.Model):
    """Sponsor profiles for deal sponsors"""
    __tablename__ = 'sponsor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    company_name = db.Column(db.String(200), nullable=False)
    company_description = db.Column(db.Text)
    company_website = db.Column(db.String(300))
    company_logo_url = db.Column(db.String(500))
    years_in_business = db.Column(db.Integer)
    total_deals = db.Column(db.Integer, default=0)
    aum = db.Column(db.String(50))  # Assets under management
    track_record = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='sponsor_profile')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])


class SponsorReview(db.Model):
    """Reviews of sponsors by investors"""
    __tablename__ = 'sponsor_reviews'

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    deal_id = db.Column(db.Integer, db.ForeignKey('investment_deals.id'))
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    review_text = db.Column(db.Text)
    is_verified_investment = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsor = db.relationship('User', foreign_keys=[sponsor_id], backref='sponsor_reviews_received')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='sponsor_reviews_given')
    deal = db.relationship('InvestmentDeal')

    __table_args__ = (db.UniqueConstraint('sponsor_id', 'reviewer_id', 'deal_id', name='unique_sponsor_review'),)


# ============================================================================
# SPECIALTY INVESTMENT ROOMS
# ============================================================================

class InvestmentRoom(db.Model):
    """Specialty-specific investment discussion rooms"""
    __tablename__ = 'investment_rooms'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # specialty, career_stage, topic
    icon = db.Column(db.String(50), default='💼')
    color = db.Column(db.String(20), default='#4A90A4')
    member_count = db.Column(db.Integer, default=0)
    post_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('RoomMembership', back_populates='room', lazy='dynamic', cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='room', lazy='dynamic', foreign_keys='Post.room_id')


class RoomMembership(db.Model):
    """User membership in investment rooms"""
    __tablename__ = 'room_memberships'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('investment_rooms.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # member, moderator, admin
    notifications_enabled = db.Column(db.Boolean, default=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='room_memberships')
    room = db.relationship('InvestmentRoom', back_populates='members')

    __table_args__ = (db.UniqueConstraint('user_id', 'room_id', name='unique_room_membership'),)


# ============================================================================
# TRENDING TOPICS & HASHTAGS
# ============================================================================

class Hashtag(db.Model):
    """Hashtags for trending topics"""
    __tablename__ = 'hashtags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # without #
    post_count = db.Column(db.Integer, default=0)
    weekly_count = db.Column(db.Integer, default=0)
    posts_today = db.Column(db.Integer, default=0)
    posts_this_week = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PostHashtag(db.Model):
    """Association between posts and hashtags"""
    __tablename__ = 'post_hashtags'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    hashtag_id = db.Column(db.Integer, db.ForeignKey('hashtags.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship('Post', backref='hashtags')
    hashtag = db.relationship('Hashtag', backref='posts')

    __table_args__ = (db.UniqueConstraint('post_id', 'hashtag_id', name='unique_post_hashtag'),)


class PostMention(db.Model):
    """User mentions (@username) in posts"""
    __tablename__ = 'post_mentions'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship('Post', backref='mentions')
    mentioned_user = db.relationship('User', backref='post_mentions')

    __table_args__ = (db.UniqueConstraint('post_id', 'mentioned_user_id', name='unique_post_mention'),)


# ============================================================================
# ACHIEVEMENT & GAMIFICATION SYSTEM
# ============================================================================

class Achievement(db.Model):
    """Available achievements/badges"""
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='🏆')
    category = db.Column(db.String(30))  # engagement, content, learning, investing, community
    points = db.Column(db.Integer, default=10)
    tier = db.Column(db.String(20), default='bronze')  # bronze, silver, gold, platinum
    is_secret = db.Column(db.Boolean, default=False)
    requirement_type = db.Column(db.String(30))  # count, threshold, action
    requirement_value = db.Column(db.Integer)
    requirement_field = db.Column(db.String(50))  # posts_count, followers_count, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserAchievement(db.Model):
    """User's earned achievements"""
    __tablename__ = 'user_achievements'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_displayed = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref='achievements')
    achievement = db.relationship('Achievement', backref='earners')

    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),)


class UserPoints(db.Model):
    """Track user points and levels"""
    __tablename__ = 'user_points'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    total_points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    weekly_points = db.Column(db.Integer, default=0)
    monthly_points = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='points_record')


class PointTransaction(db.Model):
    """Log of point transactions"""
    __tablename__ = 'point_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)  # Positive or negative
    action = db.Column(db.String(50), nullable=False)  # post_created, comment_added, like_received, etc.
    reference_type = db.Column(db.String(30))  # post, comment, achievement
    reference_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='point_transactions')


class PortfolioSnapshot(db.Model):
    """Periodic snapshots of user portfolio value"""
    __tablename__ = 'portfolio_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    snapshot_date = db.Column(db.Date, nullable=False)
    total_value = db.Column(db.Float)
    cash = db.Column(db.Float, default=0)
    stocks = db.Column(db.Float, default=0)
    bonds = db.Column(db.Float, default=0)
    real_estate = db.Column(db.Float, default=0)
    crypto = db.Column(db.Float, default=0)
    other = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='portfolio_snapshots')


# =============================================================================
# COMPATIBILITY ALIASES AND ADDITIONAL MODELS FOR NEW BLUEPRINTS
# =============================================================================

# Alias for blueprint compatibility
Room = InvestmentRoom


class PostVote(db.Model):
    """Vote on a post (upvote/downvote) for new blueprint compatibility"""
    __tablename__ = 'post_votes'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vote_type = db.Column(db.Integer)  # 1 = upvote, -1 = downvote
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', backref='votes')
    user = db.relationship('User', backref='post_votes')
    
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_post_vote'),)


class Bookmark(db.Model):
    """User bookmarks for posts"""
    __tablename__ = 'bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='bookmarks')
    post = db.relationship('Post', backref='bookmarks')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_bookmark'),)


# =============================================================================
# ADS MODELS
# =============================================================================

class AdAdvertiser(db.Model):
    """Advertisers who run ad campaigns"""
    __tablename__ = 'ad_advertisers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    category = db.Column(db.String(64), default='other')  # pharma, finance, recruiter, software, other
    compliance_status = db.Column(db.String(64), default='active')  # active, paused, restricted
    is_internal = db.Column(db.Boolean, default=False)  # Internal/platform advertisers don't pay
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    campaigns = db.relationship('AdCampaign', back_populates='advertiser', lazy='dynamic')


class AdCampaign(db.Model):
    """Ad campaigns with targeting and budget"""
    __tablename__ = 'ad_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    advertiser_id = db.Column(db.Integer, db.ForeignKey('ad_advertisers.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    start_at = db.Column(db.DateTime, default=datetime.utcnow)
    end_at = db.Column(db.DateTime, default=datetime.utcnow)
    daily_budget = db.Column(db.Float, default=0)
    targeting_json = db.Column(db.Text, default='{}')  # JSON string for targeting rules
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    advertiser = db.relationship('AdAdvertiser', back_populates='campaigns')
    creatives = db.relationship('AdCreative', back_populates='campaign', lazy='dynamic')


class AdCreative(db.Model):
    """Ad creative assets (the actual ads)"""
    __tablename__ = 'ad_creatives'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('ad_campaigns.id'), nullable=False, index=True)
    format = db.Column(db.String(64), nullable=False, index=True)  # feed, sidebar, deal_inline
    headline = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, default='')
    image_url = db.Column(db.String(1024))
    video_url = db.Column(db.String(1024))
    cta_text = db.Column(db.String(200), default='Learn more')
    landing_url = db.Column(db.String(2048), nullable=False)
    disclaimer_text = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    campaign = db.relationship('AdCampaign', back_populates='creatives')
    impressions = db.relationship('AdImpression', back_populates='creative', lazy='dynamic')
    clicks = db.relationship('AdClick', back_populates='creative', lazy='dynamic')


class AdImpression(db.Model):
    """Track ad impressions"""
    __tablename__ = 'ad_impressions'
    
    id = db.Column(db.Integer, primary_key=True)
    creative_id = db.Column(db.Integer, db.ForeignKey('ad_creatives.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    placement = db.Column(db.String(64), index=True)
    page_view_id = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    creative = db.relationship('AdCreative', back_populates='impressions')
    user = db.relationship('User', backref='ad_impressions')


class AdClick(db.Model):
    """Track ad clicks"""
    __tablename__ = 'ad_clicks'
    
    id = db.Column(db.Integer, primary_key=True)
    creative_id = db.Column(db.Integer, db.ForeignKey('ad_creatives.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    creative = db.relationship('AdCreative', back_populates='clicks')
    user = db.relationship('User', backref='ad_clicks')


# =============================================================================
# MENTIONS
# =============================================================================

class Mention(db.Model):
    __tablename__ = 'mentions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    mentioning_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
# FEED ALGORITHM MODELS
# =============================================================================

class PostScore(db.Model):
    """Pre-calculated post scores for efficient feed generation"""
    __tablename__ = 'post_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, unique=True, index=True)
    
    score = db.Column(db.Float, default=0.0, index=True)
    engagement_score = db.Column(db.Float, default=0.0)
    quality_score = db.Column(db.Float, default=1.0)
    decay_score = db.Column(db.Float, default=1.0)
    engagement_velocity = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    post = db.relationship('Post', backref=db.backref('score_record', uselist=False))


class UserInterest(db.Model):
    """Track user interests for feed personalization"""
    __tablename__ = 'user_interests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    interest_type = db.Column(db.String(20), nullable=False)
    reference_id = db.Column(db.String(100), nullable=False)
    affinity = db.Column(db.Float, default=1.0)
    
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('interests', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'interest_type', 'reference_id'),
        db.Index('idx_user_interest_lookup', 'user_id', 'interest_type'),
    )


class UserFeedPreference(db.Model):
    """User preferences for feed algorithm"""
    __tablename__ = 'user_feed_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    feed_style = db.Column(db.String(20), default='algorithmic')
    show_anonymous = db.Column(db.Boolean, default=True)
    preferred_content_types = db.Column(db.JSON, default=list)
    specialty_filter = db.Column(db.JSON, default=list)
    muted_users = db.Column(db.JSON, default=list)
    muted_rooms = db.Column(db.JSON, default=list)
    muted_hashtags = db.Column(db.JSON, default=list)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('feed_preferences', uselist=False))


# =============================================================================
# PROFILE ENHANCEMENT MODELS
# =============================================================================

class InvestmentSkill(db.Model):
    """Investment skills that users can add to their profile"""
    __tablename__ = 'investment_skills'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='general')  # industry_knowledge, tools, general
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('skills', lazy='dynamic'))
    endorsements = db.relationship('SkillEndorsement', back_populates='skill', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name'),
    )
    
    @property
    def endorsement_count(self):
        return self.endorsements.count()


class SkillEndorsement(db.Model):
    """Endorsements for user skills from other users"""
    __tablename__ = 'skill_endorsements'
    
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('investment_skills.id'), nullable=False, index=True)
    endorser_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    skill = db.relationship('InvestmentSkill', back_populates='endorsements')
    endorser = db.relationship('User', backref=db.backref('given_endorsements', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('skill_id', 'endorser_id'),
    )


class Recommendation(db.Model):
    """Professional recommendations from other physicians"""
    __tablename__ = 'recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    relationship_type = db.Column(db.String(50))  # colleague, mentor, mentee, co-investor
    content = db.Column(db.Text, nullable=False)
    is_visible = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('received_recommendations', lazy='dynamic'))
    author = db.relationship('User', foreign_keys=[author_id], backref=db.backref('given_recommendations', lazy='dynamic'))


class EngagementSnapshot(db.Model):
    """Hourly snapshots of post engagement for velocity calculation"""
    __tablename__ = 'engagement_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, index=True)
    
    snapshot_hour = db.Column(db.DateTime, nullable=False)
    
    upvotes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    bookmarks = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', backref=db.backref('engagement_history', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('post_id', 'snapshot_hour'),
        db.Index('idx_engagement_time', 'post_id', 'snapshot_hour'),
    )


class OpMedArticle(db.Model):
    """Op-MedInvest articles - essays from medical professionals about investing"""
    __tablename__ = 'opmed_articles'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(350), unique=True, nullable=False)
    excerpt = db.Column(db.Text)  # Short summary for cards
    content = db.Column(db.Text, nullable=False)
    
    # Ghost integration
    ghost_id = db.Column(db.String(100), unique=True, index=True)  # Ghost post ID for syncing
    
    # Media
    cover_image_url = db.Column(db.String(500))
    
    # Categorization
    category = db.Column(db.String(50), default='general')  # general, market_insights, retirement, real_estate, tax_strategy, from_editors
    specialty_tag = db.Column(db.String(100))  # Author's specialty
    
    # Status - editorial workflow
    status = db.Column(db.String(20), default='draft')  # draft, submitted, under_review, revision_requested, approved, published, rejected
    is_featured = db.Column(db.Boolean, default=False)
    is_editors_pick = db.Column(db.Boolean, default=False)
    
    # Editorial workflow
    submitted_at = db.Column(db.DateTime)  # When author submitted for review
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Editor who reviewed
    reviewed_at = db.Column(db.DateTime)
    editor_notes = db.Column(db.Text)  # Internal notes for editors
    revision_count = db.Column(db.Integer, default=0)  # Number of revisions
    word_count = db.Column(db.Integer, default=0)
    reading_time_minutes = db.Column(db.Integer, default=0)
    
    # SEO
    meta_description = db.Column(db.String(300))
    meta_keywords = db.Column(db.String(200))
    
    # Engagement
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    share_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    
    author = db.relationship('User', foreign_keys=[author_id], backref=db.backref('opmed_articles', lazy='dynamic'))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by_id], backref=db.backref('opmed_reviewed', lazy='dynamic'))
    
    def calculate_reading_time(self):
        """Calculate estimated reading time based on word count"""
        if self.content:
            import re
            words = len(re.findall(r'\w+', self.content))
            self.word_count = words
            self.reading_time_minutes = max(1, words // 200)  # Avg 200 words per minute
    
    def generate_slug(self):
        """Generate URL-friendly slug from title"""
        import re
        slug = self.title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        # Add timestamp for uniqueness
        from datetime import datetime
        slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        return slug[:350]


class OpMedArticleLike(db.Model):
    """Likes on Op-MedInvest articles"""
    __tablename__ = 'opmed_article_likes'
    
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('opmed_articles.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    article = db.relationship('OpMedArticle', backref=db.backref('likes', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('opmed_article_likes', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('article_id', 'user_id'),
    )


class OpMedEditorialFeedback(db.Model):
    """Editor feedback on Op-MedInvest article submissions"""
    __tablename__ = 'opmed_editorial_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('opmed_articles.id'), nullable=False, index=True)
    editor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    feedback_type = db.Column(db.String(30), default='general')  # general, structure, content, grammar, revision_request
    feedback = db.Column(db.Text, nullable=False)
    
    # For revision requests
    is_revision_required = db.Column(db.Boolean, default=False)
    revision_areas = db.Column(db.Text)  # JSON list of areas needing revision
    
    # Status tracking
    decision = db.Column(db.String(20))  # approve, revise, reject
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    article = db.relationship('OpMedArticle', backref=db.backref('editorial_feedback', lazy='dynamic'))
    editor = db.relationship('User', backref=db.backref('opmed_feedback_given', lazy='dynamic'))


class OpMedSubscriber(db.Model):
    """Email subscribers for Op-MedInvest newsletter"""
    __tablename__ = 'opmed_subscribers'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Optional link to user account
    
    is_active = db.Column(db.Boolean, default=True)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    unsubscribed_at = db.Column(db.DateTime)
    
    # Preferences
    weekly_digest = db.Column(db.Boolean, default=True)
    new_articles = db.Column(db.Boolean, default=True)
    editors_picks_only = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('opmed_subscription', uselist=False))


class OpMedComment(db.Model):
    """Comments on Op-MedInvest articles"""
    __tablename__ = 'opmed_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('opmed_articles.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    content = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    article = db.relationship('OpMedArticle', backref=db.backref('comments', lazy='dynamic'))
    author = db.relationship('User', backref=db.backref('opmed_comments', lazy='dynamic'))


class PushSubscription(db.Model):
    """Web push notification subscriptions"""
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    endpoint = db.Column(db.Text, nullable=False)
    p256dh_key = db.Column(db.String(500), nullable=False)
    auth_key = db.Column(db.String(500), nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    user = db.relationship('User', backref=db.backref('push_subscriptions', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='unique_user_endpoint'),
    )


class LoginSession(db.Model):
    """Track user login sessions and activity"""
    __tablename__ = 'login_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    device_type = db.Column(db.String(50))
    browser = db.Column(db.String(100))
    os = db.Column(db.String(100))
    location = db.Column(db.String(200))
    
    login_method = db.Column(db.String(30))
    is_successful = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(100))
    
    is_current = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('login_sessions', lazy='dynamic'))


class AuthorizedApp(db.Model):
    """Third-party apps authorized to access user accounts"""
    __tablename__ = 'authorized_apps'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    app_name = db.Column(db.String(100), nullable=False)
    app_id = db.Column(db.String(100))
    scopes = db.Column(db.Text)
    
    authorized_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    user = db.relationship('User', backref=db.backref('authorized_apps', lazy='dynamic'))


class SiteSettings(db.Model):
    """Site-wide configuration settings"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    youtube_channel_id = db.Column(db.String(50))
    youtube_channel_name = db.Column(db.String(200))
    youtube_live_enabled = db.Column(db.Boolean, default=True)
    
    show_playlist_id = db.Column(db.String(50))
    show_name = db.Column(db.String(200), default='The Medicine and Money Show')
    show_episodes_enabled = db.Column(db.Boolean, default=True)
    show_episodes_limit = db.Column(db.Integer, default=12)
    
    # Buzzsprout podcast integration
    buzzsprout_podcast_id = db.Column(db.String(50))
    buzzsprout_podcast_name = db.Column(db.String(200))
    buzzsprout_enabled = db.Column(db.Boolean, default=False)
    buzzsprout_episodes_limit = db.Column(db.Integer, default=12)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    updated_by = db.relationship('User')


class CodeQualityIssue(db.Model):
    """Track code quality issues and recommendations from automated reviews"""
    __tablename__ = 'code_quality_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Issue details
    issue_type = db.Column(db.String(50), nullable=False)  # bug, security, performance, style, feature_suggestion
    severity = db.Column(db.String(20), default='medium')  # critical, high, medium, low, info
    status = db.Column(db.String(20), default='open')  # open, in_progress, fixed, ignored, wont_fix
    
    # Location
    file_path = db.Column(db.String(500))
    line_number = db.Column(db.Integer)
    function_name = db.Column(db.String(200))
    
    # Description
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    code_snippet = db.Column(db.Text)
    suggested_fix = db.Column(db.Text)
    
    # AI analysis
    ai_confidence = db.Column(db.Float)  # 0.0 to 1.0
    ai_reasoning = db.Column(db.Text)
    
    # Auto-fix tracking
    auto_fixable = db.Column(db.Boolean, default=False)
    auto_fixed = db.Column(db.Boolean, default=False)
    auto_fixed_at = db.Column(db.DateTime)
    fix_commit_hash = db.Column(db.String(40))
    
    # Timestamps
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    
    # Tracking
    review_run_id = db.Column(db.String(50))  # Groups issues from same review run
    
    # Database indexes for query optimization
    __table_args__ = (
        db.Index('idx_issue_status_severity', 'status', 'severity'),
        db.Index('idx_issue_file_path', 'file_path'),
        db.Index('idx_issue_review_run', 'review_run_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'issue_type': self.issue_type,
            'severity': self.severity,
            'status': self.status,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'title': self.title,
            'description': self.description,
            'suggested_fix': self.suggested_fix,
            'auto_fixable': self.auto_fixable,
            'auto_fixed': self.auto_fixed,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None
        }


class CodeReviewRun(db.Model):
    """Track each code review run"""
    __tablename__ = 'code_review_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(50), unique=True, nullable=False)
    
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    status = db.Column(db.String(20), default='running')  # running, completed, failed
    
    files_analyzed = db.Column(db.Integer, default=0)
    issues_found = db.Column(db.Integer, default=0)
    issues_fixed = db.Column(db.Integer, default=0)
    
    summary = db.Column(db.Text)
    error_message = db.Column(db.Text)
    
    # Config used for this run
    config_snapshot = db.Column(db.Text)  # JSON of settings used


class AIAuditLog(db.Model):
    """Track all AI operations for auditing and debugging"""
    __tablename__ = 'ai_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User association (optional - may be system operations)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Operation details
    action_type = db.Column(db.String(100), nullable=False)  # code_review, chat, content_moderation, etc.
    model_name = db.Column(db.String(100))  # gemini-2.0-flash, gpt-4, etc.
    
    # Input tracking (hash for privacy)
    input_hash = db.Column(db.String(64))  # SHA256 hash of input
    input_length = db.Column(db.Integer)  # Character count of input
    input_file_path = db.Column(db.String(500))  # For file-based operations
    
    # Output tracking
    output_summary = db.Column(db.Text)  # Brief summary of output
    output_length = db.Column(db.Integer)  # Character count of output
    issues_detected = db.Column(db.Integer, default=0)  # For code review
    
    # Token usage
    tokens_used = db.Column(db.Integer)
    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)
    
    # Performance
    latency_ms = db.Column(db.Integer)  # Response time in milliseconds
    
    # Status
    status = db.Column(db.String(20), default='success')  # success, error, timeout
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('ai_audit_logs', lazy='dynamic'))
    
    __table_args__ = (
        db.Index('idx_ai_audit_action_date', 'action_type', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action_type': self.action_type,
            'model_name': self.model_name,
            'tokens_used': self.tokens_used,
            'latency_ms': self.latency_ms,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# =============================================================================
# PETITION SYSTEM MODELS
# =============================================================================

class UserMedicalLicense(db.Model):
    """Multiple medical licenses per user for different states"""
    __tablename__ = 'user_medical_licenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    license_number = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(2), nullable=False)  # Two-letter state code
    license_type = db.Column(db.String(50), default='MD')  # MD, DO, etc.
    expiration_date = db.Column(db.Date)
    is_primary = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_document_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('medical_licenses', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'license_number', 'state', name='unique_user_license'),
    )


class Petition(db.Model):
    """Petitions that can be assigned to rooms for users to sign"""
    __tablename__ = 'petitions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_recipient = db.Column(db.String(200))  # Who the petition is addressed to
    goal_signatures = db.Column(db.Integer, default=100)
    
    room_id = db.Column(db.Integer, db.ForeignKey('investment_rooms.id'), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    status = db.Column(db.String(20), default='draft')  # draft, active, closed, delivered
    is_active = db.Column(db.Boolean, default=True)
    
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    
    signature_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    room = db.relationship('InvestmentRoom', backref=db.backref('petitions', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('created_petitions', lazy='dynamic'))
    signatures = db.relationship('PetitionSignature', back_populates='petition', lazy='dynamic', cascade='all, delete-orphan')


class MIAConnection(db.Model):
    """Market Inefficiency Agents platform connection (PREMIUM FEATURE)"""
    __tablename__ = 'mia_connections'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    api_key = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=False)
    
    enabled_markets = db.Column(db.Text)
    enabled_agents = db.Column(db.Text)
    
    show_in_feed = db.Column(db.Boolean, default=True)
    alert_frequency = db.Column(db.String(20), default='realtime')
    min_confidence = db.Column(db.Integer, default=50)
    
    connected_at = db.Column(db.DateTime)
    last_sync_at = db.Column(db.DateTime)
    sync_status = db.Column(db.String(50), default='pending')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('mia_connection', uselist=False))


class MIAAlert(db.Model):
    """Cached MIA alerts/triggers for feed display"""
    __tablename__ = 'mia_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True)
    
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text)
    severity = db.Column(db.String(20), default='info')
    market = db.Column(db.String(100))
    agent_name = db.Column(db.String(100))
    confidence = db.Column(db.Integer, default=0)
    
    alert_type = db.Column(db.String(50))
    extra_data = db.Column(db.Text)
    
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)


class PetitionSignature(db.Model):
    """Signatures on petitions"""
    __tablename__ = 'petition_signatures'
    
    id = db.Column(db.Integer, primary_key=True)
    petition_id = db.Column(db.Integer, db.ForeignKey('petitions.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    address_line1 = db.Column(db.String(200), nullable=False)
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    
    license_number = db.Column(db.String(50), nullable=False)
    license_state = db.Column(db.String(2), nullable=False)
    
    comments = db.Column(db.Text)  # Optional additional comments
    is_public = db.Column(db.Boolean, default=True)  # Show name publicly
    
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # For verification
    
    petition = db.relationship('Petition', back_populates='signatures')
    user = db.relationship('User', backref=db.backref('petition_signatures', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('petition_id', 'user_id', name='unique_petition_signature'),
    )


class Webhook(db.Model):
    """Webhook configuration for external integrations"""
    __tablename__ = 'webhooks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.Text)
    secret = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_triggered = db.Column(db.DateTime)
    last_status = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    deliveries = db.relationship('WebhookDelivery', backref='webhook', lazy='dynamic')


class WebhookDelivery(db.Model):
    """Webhook delivery log"""
    __tablename__ = 'webhook_deliveries'
    
    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey('webhooks.id'), nullable=False)
    event = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text)
    status_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    duration_ms = db.Column(db.Integer)
    success = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomRole(db.Model):
    """Custom user roles with configurable permissions"""
    __tablename__ = 'custom_roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.Column(db.Text)
    color = db.Column(db.String(20), default='#6c757d')
    priority = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BlockedKeyword(db.Model):
    """Content filtering keywords for moderation"""
    __tablename__ = 'blocked_keywords'
    
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), unique=True, nullable=False)
    severity = db.Column(db.String(20), default='low')  # low, medium, high, critical
    action = db.Column(db.String(20), default='flag')  # flag, hide, block
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_by = db.relationship('User', backref='created_keywords')
