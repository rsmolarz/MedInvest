from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


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
    
    # Relationships
    progress = db.relationship('UserProgress', back_populates='user', lazy='dynamic')
    forum_posts = db.relationship('ForumPost', back_populates='author', lazy='dynamic')
    transactions = db.relationship('PortfolioTransaction', back_populates='user', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    likes = db.relationship('Like', back_populates='user', lazy='dynamic')
    
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
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    post_type = db.Column(db.String(20), default='general')  # general, question, insight, achievement
    tags = db.Column(db.String(500))  # Comma-separated tags
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', back_populates='posts')
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