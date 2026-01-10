from datetime import datetime, timedelta
import secrets
import string
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import pyotp


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    medical_license = db.Column(db.String(50), unique=True, nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    # Trust & verification
    npi_number = db.Column(db.String(20), unique=True)
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
    # Reputation score (cached). Always derived from ReputationEvent stream.
    reputation_score = db.Column(db.Integer, default=0)
    # Invite-only growth
    invite_credits = db.Column(db.Integer, default=2)
    invite_id = db.Column(db.Integer, db.ForeignKey('invites.id'))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Two-Factor Authentication fields
    totp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    
    # Password reset fields
    password_reset_token = db.Column(db.String(100))
    password_reset_expires = db.Column(db.DateTime)
    
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


# Social Media Models
class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    visibility = db.Column(db.String(20), default='physicians')  # public, physicians, group
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    post_type = db.Column(db.String(20), default='general')  # general, question, insight, achievement, deal
    tags = db.Column(db.String(500))  # Comma-separated tags
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', back_populates='posts')
    group = db.relationship('Group', back_populates='posts')
    comments = db.relationship('Comment', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    
    def likes_count(self):
        return self.likes.count()
    
    def comments_count(self):
        return self.comments.count()
    
    def is_liked_by(self, user):
        return self.likes.filter_by(user_id=user.id).first() is not None


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    content = db.Column(db.Text, nullable=False)
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
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notification_type = db.Column(db.String(50), nullable=False)  # like, comment, follow, mention
    message = db.Column(db.String(500), nullable=False)
    related_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    sender = db.relationship('User', foreign_keys=[sender_id])
    related_post = db.relationship('Post')


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

