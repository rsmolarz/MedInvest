"""
MedInvest Database Models
"""
from datetime import datetime
from enum import Enum
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import secrets
import string
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# =============================================================================
# ENUMS
# =============================================================================

class SubscriptionTier(Enum):
    FREE = 'free'
    PREMIUM = 'premium'


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


# =============================================================================
# USER MODEL
# =============================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Profile
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    specialty = db.Column(db.String(50))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(500))
    
    # Verification
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Subscription
    subscription_tier = db.Column(db.Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_ends_at = db.Column(db.DateTime)
    
    # Gamification
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    login_streak = db.Column(db.Integer, default=0)
    
    # Referral
    referral_code = db.Column(db.String(10), unique=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_premium(self):
        if self.subscription_tier == SubscriptionTier.PREMIUM:
            if self.subscription_ends_at is None or self.subscription_ends_at > datetime.utcnow():
                return True
        return False
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_referral_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            if not User.query.filter_by(referral_code=code).first():
                self.referral_code = code
                break
    
    def add_points(self, amount):
        self.points += amount
        # Level up every 500 points
        self.level = (self.points // 500) + 1


# =============================================================================
# ROOMS & POSTS
# =============================================================================

class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # Strategy, Specialty, Career Stage
    icon = db.Column(db.String(50))
    
    is_premium_only = db.Column(db.Boolean, default=False)
    member_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    posts = db.relationship('Post', backref='room', lazy='dynamic')


class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    
    # Content
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    
    # Post type for social media style
    post_type = db.Column(db.String(20), default='text')  # 'text', 'image', 'video', 'gallery'
    
    is_anonymous = db.Column(db.Boolean, default=False)
    anonymous_name = db.Column(db.String(50))  # e.g., "Anonymous Cardiologist"
    
    # Engagement
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    share_count = db.Column(db.Integer, default=0)
    
    # Media count for quick reference
    media_count = db.Column(db.Integer, default=0)
    
    is_pinned = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    votes = db.relationship('PostVote', backref='post', lazy='dynamic')
    
    @property
    def score(self):
        return self.upvotes - self.downvotes
    
    @property
    def display_author(self):
        if self.is_anonymous:
            return self.anonymous_name or "Anonymous"
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


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'))  # For nested comments
    
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    
    upvotes = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')


class PostVote(db.Model):
    __tablename__ = 'post_votes'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vote_type = db.Column(db.Integer)  # 1 = upvote, -1 = downvote
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id'),)


# =============================================================================
# EXPERT AMAs
# =============================================================================

class ExpertAMA(db.Model):
    __tablename__ = 'expert_amas'
    
    id = db.Column(db.Integer, primary_key=True)
    
    expert_name = db.Column(db.String(100), nullable=False)
    expert_title = db.Column(db.String(200))
    expert_bio = db.Column(db.Text)
    expert_image_url = db.Column(db.String(500))
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.Enum(AMAStatus), default=AMAStatus.SCHEDULED)
    
    is_premium_only = db.Column(db.Boolean, default=False)
    
    recording_url = db.Column(db.String(500))
    
    participant_count = db.Column(db.Integer, default=0)
    question_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    questions = db.relationship('AMAQuestion', backref='ama', lazy='dynamic')
    registrations = db.relationship('AMARegistration', backref='ama', lazy='dynamic')


class AMAQuestion(db.Model):
    __tablename__ = 'ama_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    ama_id = db.Column(db.Integer, db.ForeignKey('expert_amas.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_answered = db.Column(db.Boolean, default=False)
    upvotes = db.Column(db.Integer, default=0)
    
    asked_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref='ama_questions')


class AMARegistration(db.Model):
    __tablename__ = 'ama_registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    ama_id = db.Column(db.Integer, db.ForeignKey('expert_amas.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    attended = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='ama_registrations')
    
    __table_args__ = (db.UniqueConstraint('ama_id', 'user_id'),)


# =============================================================================
# INVESTMENT DEALS
# =============================================================================

class InvestmentDeal(db.Model):
    __tablename__ = 'investment_deals'
    
    id = db.Column(db.Integer, primary_key=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    deal_type = db.Column(db.String(50))  # real_estate, fund, practice, syndicate
    
    minimum_investment = db.Column(db.Float, nullable=False)
    target_raise = db.Column(db.Float)
    current_raised = db.Column(db.Float, default=0)
    projected_return = db.Column(db.String(100))
    investment_term = db.Column(db.String(50))
    
    location = db.Column(db.String(200))
    
    sponsor_name = db.Column(db.String(100))
    sponsor_bio = db.Column(db.Text)
    sponsor_contact = db.Column(db.String(200))
    
    status = db.Column(db.Enum(DealStatus), default=DealStatus.DRAFT, index=True)
    is_featured = db.Column(db.Boolean, default=False)
    
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    view_count = db.Column(db.Integer, default=0)
    interest_count = db.Column(db.Integer, default=0)
    
    interests = db.relationship('DealInterest', backref='deal', lazy='dynamic')


class DealInterest(db.Model):
    __tablename__ = 'deal_interests'
    
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('investment_deals.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    investment_amount = db.Column(db.Float)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='interested')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='deal_interests')
    
    __table_args__ = (db.UniqueConstraint('deal_id', 'user_id'),)


# =============================================================================
# COURSES
# =============================================================================

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    instructor_name = db.Column(db.String(100))
    instructor_bio = db.Column(db.Text)
    
    price = db.Column(db.Float, nullable=False)
    
    thumbnail_url = db.Column(db.String(500))
    
    total_modules = db.Column(db.Integer, default=0)
    total_duration_minutes = db.Column(db.Integer, default=0)
    
    difficulty_level = db.Column(db.String(20))  # beginner, intermediate, advanced
    
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    
    enrolled_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    modules = db.relationship('CourseModule', backref='course', lazy='dynamic', order_by='CourseModule.order_index')
    enrollments = db.relationship('CourseEnrollment', backref='course', lazy='dynamic')


class CourseModule(db.Model):
    __tablename__ = 'course_modules'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    
    video_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    
    order_index = db.Column(db.Integer, default=0)


class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    purchase_price = db.Column(db.Float)
    
    progress_percent = db.Column(db.Float, default=0)
    completed_modules = db.Column(db.JSON, default=list)
    
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='course_enrollments')
    
    __table_args__ = (db.UniqueConstraint('course_id', 'user_id'),)


# =============================================================================
# EVENTS
# =============================================================================

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    is_virtual = db.Column(db.Boolean, default=True)
    venue_name = db.Column(db.String(200))
    venue_address = db.Column(db.String(500))
    
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    
    regular_price = db.Column(db.Float, nullable=False)
    early_bird_price = db.Column(db.Float)
    early_bird_ends = db.Column(db.DateTime)
    
    max_attendees = db.Column(db.Integer)
    current_attendees = db.Column(db.Integer, default=0)
    
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    registrations = db.relationship('EventRegistration', backref='event', lazy='dynamic')


class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    ticket_type = db.Column(db.String(20), default='regular')
    purchase_price = db.Column(db.Float)
    
    attended = db.Column(db.Boolean, default=False)
    
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='event_registrations')
    
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id'),)


# =============================================================================
# MENTORSHIP
# =============================================================================

class Mentorship(db.Model):
    __tablename__ = 'mentorships'
    
    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    focus_areas = db.Column(db.String(500))
    status = db.Column(db.Enum(MentorshipStatus), default=MentorshipStatus.PENDING)
    
    start_date = db.Column(db.DateTime)
    
    total_sessions = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    mentor = db.relationship('User', foreign_keys=[mentor_id], backref='mentoring')
    mentee = db.relationship('User', foreign_keys=[mentee_id], backref='mentored_by')


# =============================================================================
# REFERRALS
# =============================================================================

class Referral(db.Model):
    __tablename__ = 'referrals'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    referred_user_activated = db.Column(db.Boolean, default=False)
    referred_user_premium = db.Column(db.Boolean, default=False)
    
    reward_value = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred_user = db.relationship('User', foreign_keys=[referred_user_id])


# =============================================================================
# PORTFOLIO
# =============================================================================

class PortfolioSnapshot(db.Model):
    __tablename__ = 'portfolio_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
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
# POST MEDIA (Images & Videos)
# =============================================================================

class PostMedia(db.Model):
    __tablename__ = 'post_media'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    media_type = db.Column(db.String(20), nullable=False)  # 'image' or 'video'
    file_path = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255))
    
    # For images
    thumbnail_path = db.Column(db.String(500))
    
    # For videos
    duration_seconds = db.Column(db.Integer)  # Max 60 seconds for short videos
    video_thumbnail = db.Column(db.String(500))
    
    # Metadata
    file_size = db.Column(db.Integer)  # In bytes
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    
    order_index = db.Column(db.Integer, default=0)  # For carousel ordering
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', backref=db.backref('media', lazy='dynamic', order_by='PostMedia.order_index'))


# =============================================================================
# BOOKMARKS
# =============================================================================

class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='bookmarks')
    post = db.relationship('Post', backref='bookmarks')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)
