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
    # Verification ops
    can_review_verifications = db.Column(db.Boolean, default=False)
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
    reputation_events = db.relationship('ReputationEvent', back_populates='user', lazy='dynamic')
    invites_sent = db.relationship('Invite', back_populates='inviter', lazy='dynamic', foreign_keys='Invite.inviter_user_id')
    invite = db.relationship('Invite', foreign_keys=[invite_id])
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    likes = db.relationship('Like', back_populates='user', lazy='dynamic')
    # Group and messaging relationships
    group_memberships = db.relationship('GroupMembership', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    sent_connections = db.relationship('Connection', foreign_keys='Connection.requester_id', backref=db.backref('requester', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    received_connections = db.relationship('Connection', foreign_keys='Connection.addressee_id', backref=db.backref('addressee', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    dm_participations = db.relationship('DirectMessageParticipant', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    
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
    # Moderation controls
    is_hidden = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    downrank_score = db.Column(db.Float, default=0.0)
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
    # Moderation controls
    is_hidden = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    downrank_score = db.Column(db.Float, default=0.0)
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

# ----------------------
# Invite-only growth
# ----------------------

class Invite(db.Model):
    __tablename__ = 'invites'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    invitee_email = db.Column(db.String(255))
    status = db.Column(db.String(20), default='issued', index=True)  # issued, accepted, expired, revoked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    accepted_at = db.Column(db.DateTime)

    inviter = db.relationship('User', back_populates='invites_sent', foreign_keys=[inviter_user_id])

    @staticmethod
    def new_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))


# ----------------------
# Weekly Digest (retention)
# ----------------------

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
    item_type = db.Column(db.String(20), nullable=False, index=True)  # deal, comment, summary
    entity_id = db.Column(db.Integer)  # deal_id or comment_id (nullable for summary)
    score = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer)
    payload_json = db.Column(db.Text)  # for summary or extra rendering data
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

    # Idempotency & de-duplication
    # If the client supplies an idempotency_key, we guarantee the same request
    # will return the same queued/running job (until completion) rather than
    # enqueue duplicates.
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

    __table_args__ = (
        # Best-effort uniqueness for idempotent requests (NULLs allowed)
        db.Index('ix_ai_jobs_creator_type_fingerprint', 'created_by_id', 'job_type', 'request_fingerprint'),
    )


# ----------------------
# Activity logging (analytics)
# ----------------------

class UserActivity(db.Model):
    __tablename__ = 'user_activity'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    activity_type = db.Column(db.String(30), nullable=False, index=True)  # view, post, comment, endorse, deal_create, ai_run, invite_accept
    entity_type = db.Column(db.String(20), index=True)  # deal, post, comment, digest, invite
    entity_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ----------------------
# Alerts (ops)
# ----------------------

class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(40), nullable=False, index=True)  # verification_sla
    metric = db.Column(db.String(10), nullable=False, index=True)  # p50, p95
    value_hours = db.Column(db.Float, nullable=False)
    threshold_hours = db.Column(db.Float, nullable=False)
    window_start = db.Column(db.DateTime, nullable=False, index=True)
    window_end = db.Column(db.DateTime, nullable=False, index=True)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('alert_type', 'metric', 'window_start', 'window_end', name='uq_alert_window'),
    )


# ----------------------
# Onboarding prompts (cohort-aware nudges)
# ----------------------

class OnboardingPrompt(db.Model):
    __tablename__ = 'onboarding_prompts'

    id = db.Column(db.Integer, primary_key=True)
    cohort_dimension = db.Column(db.String(30), nullable=False, index=True)  # specialty, invite_source, role
    cohort_value = db.Column(db.String(120), nullable=False, index=True)
    prompt_type = db.Column(db.String(20), default='banner')  # banner, modal, nudge
    copy = db.Column(db.Text, nullable=False)
    cta_text = db.Column(db.String(80))
    cta_target = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserPromptDismissal(db.Model):
    __tablename__ = 'user_prompt_dismissals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('onboarding_prompts.id'), nullable=False, index=True)
    dismissed_until = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'prompt_id', name='uq_user_prompt'),
    )


# ----------------------
# Invite credit events (growth tuning)
# ----------------------

class InviteCreditEvent(db.Model):
    __tablename__ = 'invite_credit_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(30), nullable=False, index=True)  # cohort_bonus, manual, promo
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ----------------------
# Verification queue (ops routing)
# ----------------------

class VerificationQueueEntry(db.Model):
    __tablename__ = 'verification_queue'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    assigned_reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, assigned, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    assigned_at = db.Column(db.DateTime)

    user = db.relationship('User', foreign_keys=[user_id])
    reviewer = db.relationship('User', foreign_keys=[assigned_reviewer_id])


# ----------------------
# Auto-moderation
# ----------------------

class CohortNorm(db.Model):
    __tablename__ = 'cohort_norms'

    id = db.Column(db.Integer, primary_key=True)
    cohort_dimension = db.Column(db.String(20), nullable=False, index=True)  # specialty, role
    cohort_value = db.Column(db.String(120), nullable=False, index=True)
    min_reputation_to_post = db.Column(db.Integer, default=0)
    max_reports_before_hide = db.Column(db.Integer, default=3)
    auto_lock_threshold = db.Column(db.Float, default=-5.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('cohort_dimension', 'cohort_value', name='uq_cohort_norm'),
    )


class ModerationEvent(db.Model):
    __tablename__ = 'moderation_events'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # post, comment, deal
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    signal_score = db.Column(db.Float, default=0.0)
    action = db.Column(db.String(20), default='none', index=True)  # none, downrank, hide, review, lock
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class ContentReport(db.Model):
    """User-submitted reports on posts/comments.

    Note: The Alembic migrations in this repo create the table name `content_report`
    (singular). Earlier scaffolding used `content_reports` and different column names.
    This model matches the current routes + migrations.
    """

    __tablename__ = 'content_report'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # post, comment
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    reporter_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    reason = db.Column(db.String(120))
    details = db.Column(db.Text)

    status = db.Column(db.String(20), default='open', index=True)  # open, resolved
    resolution = db.Column(db.String(40))  # no_action, hide, lock
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)

    reporter = db.relationship('User', foreign_keys=[reporter_user_id])
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])

    __table_args__ = (
        db.UniqueConstraint('reporter_user_id', 'entity_type', 'entity_id', name='uq_content_report_once'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'reporter_user_id': self.reporter_user_id,
            'reason': self.reason,
            'details': self.details,
            'status': self.status,
            'resolution': self.resolution,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() + 'Z' if self.resolved_at else None,
            'resolved_by_id': self.resolved_by_id,
        }


# ----------------------
# Deal outcomes (closed -> lessons)
# ----------------------

class DealOutcome(db.Model):
    __tablename__ = 'deal_outcomes'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal_details.id'), nullable=False, unique=True, index=True)
    outcome = db.Column(db.String(20), nullable=False, index=True)  # proceeded, passed, failed, exceeded
    actual_irr = db.Column(db.Float)
    actual_multiple = db.Column(db.Float)
    time_to_close_months = db.Column(db.Integer)
    what_went_right = db.Column(db.Text)
    what_went_wrong = db.Column(db.Text)
    key_lessons = db.Column(db.Text, nullable=False)
    reported_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    deal = db.relationship('DealDetails', foreign_keys=[deal_id])
    reporter = db.relationship('User', foreign_keys=[reported_by_user_id])


# ----------------------
# Sponsor vetting
# ----------------------

class SponsorProfile(db.Model):
    __tablename__ = 'sponsor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    firm_name = db.Column(db.String(200))
    years_experience = db.Column(db.Integer)
    asset_classes_json = db.Column(db.Text)  # JSON list
    aum_estimate = db.Column(db.String(60))
    references = db.Column(db.Text)
    status = db.Column(db.String(20), default='candidate', index=True)  # candidate, vetted, restricted
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


class SponsorReview(db.Model):
    __tablename__ = 'sponsor_reviews'

    id = db.Column(db.Integer, primary_key=True)
    sponsor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reviewer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    verified_investor = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('sponsor_user_id', 'reviewer_user_id', name='uq_sponsor_review_once'),
    )

    sponsor = db.relationship('User', foreign_keys=[sponsor_user_id])
    reviewer = db.relationship('User', foreign_keys=[reviewer_user_id])
