from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from models import User, Module, UserProgress, ForumTopic, ForumPost, PortfolioTransaction, Resource, Post, Comment, Like, Follow, Notification, Group, GroupMembership, Connection, DealDetails, DealAnalysis, AiJob, ReputationEvent, Invite, Digest, DigestItem, UserActivity, Alert, ExpertAMA, AMAQuestion, AMARegistration, InvestmentDeal, DealInterest, Mentorship, MentorshipSession, Course, CourseModule, CourseEnrollment, Event, EventSession, EventRegistration, Referral, Subscription, Payment, VerificationQueueEntry, OnboardingPrompt, UserPromptDismissal, InviteCreditEvent, CohortNorm, ModerationEvent, ContentReport, DealOutcome, SponsorProfile, SponsorReview, InvestmentRoom, RoomMembership, Hashtag, PostHashtag, Achievement, UserAchievement, UserPoints, PointTransaction
from datetime import datetime, timedelta
import json
import math
import logging
import os
from markupsafe import Markup
import re
import pyotp
import qrcode
import io
import base64
import requests

from access_control import require_verified, require_roles
from ai_service import summarize_text, analyze_deal
from authorization import can, Actions, deny_response
from ai_jobs import enqueue_ai_job, process_job


def get_sendgrid_credentials():
    """Get SendGrid API key and from email from Replit connector"""
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    x_replit_token = None
    
    if os.environ.get('REPL_IDENTITY'):
        x_replit_token = 'repl ' + os.environ.get('REPL_IDENTITY')
    elif os.environ.get('WEB_REPL_RENEWAL'):
        x_replit_token = 'depl ' + os.environ.get('WEB_REPL_RENEWAL')
    
    if not x_replit_token or not hostname:
        return None, None
    
    try:
        response = requests.get(
            f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=sendgrid',
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            }
        )
        data = response.json()
        connection = data.get('items', [None])[0]
        
        if connection and connection.get('settings'):
            api_key = connection['settings'].get('api_key')
            from_email = connection['settings'].get('from_email')
            return api_key, from_email
    except Exception as e:
        logging.error(f"Failed to get SendGrid credentials: {e}")
    
    return None, None


def send_password_reset_email(user, reset_url):
    """Send password reset email via SendGrid"""
    api_key, from_email = get_sendgrid_credentials()
    
    if not api_key or not from_email:
        logging.warning("SendGrid not configured, logging reset URL instead")
        logging.info(f"Password reset URL for {user.email}: {reset_url}")
        return False
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=from_email,
            to_emails=user.email,
            subject='Reset Your MedInvest Password',
            html_content=f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2c5282;">Password Reset Request</h2>
                <p>Hello {user.first_name or user.username},</p>
                <p>We received a request to reset your password for your MedInvest account.</p>
                <p>Click the button below to reset your password:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="background-color: #4299e1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                </p>
                <p>If you didn't request this, you can safely ignore this email. The link will expire in 1 hour.</p>
                <p>Best regards,<br>The MedInvest Team</p>
            </div>
            '''
        )
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logging.info(f"Password reset email sent to {user.email}, status: {response.status_code}")
        return response.status_code in [200, 201, 202]
    except Exception as e:
        logging.error(f"Failed to send password reset email: {e}")
        logging.info(f"Password reset URL for {user.email}: {reset_url}")
        return False

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Add Jinja2 filter for newline to break conversion
@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to <br> tags."""
    if text is None:
        return ''
    text = str(text).replace('\n', '<br>')
    return Markup(text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/health')
def health_check():
    """Fast health check endpoint for deployment"""
    # Quick response without database check for faster health checks
    return {'status': 'healthy', 'app': 'medinvest'}, 200

@app.route('/health/deep')
def health_check_deep():
    """Detailed health check with database verification"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat(), 'database': 'connected'}, 200
    except Exception as e:
        logging.error(f"Deep health check failed: {e}")
        return {'status': 'unhealthy', 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}, 503

@app.route('/readiness')
def readiness_check():
    """Readiness check for deployment"""
    return {'status': 'ready', 'app': 'medinvest', 'version': '1.0'}, 200

@app.route('/status')
def status_check():
    """Detailed status for deployment debugging"""
    import sys
    import platform
    return {
        'status': 'running',
        'python_version': sys.version,
        'platform': platform.platform(),
        'app_name': 'MedInvest',
        'deployment': os.environ.get('REPLIT_DEPLOYMENT', 'development'),
        'port': os.environ.get('PORT', '5000'),
        'routes_count': len([rule.rule for rule in app.url_map.iter_rules()]),
        'timestamp': datetime.utcnow().isoformat()
    }, 200

@app.route('/')
def index():
    """Main landing page with health check capability"""
    try:
        # Quick health check response for deployment probes
        if request.headers.get('User-Agent', '').startswith(('GoogleHC', 'kube-probe', 'Cloud-Run')):
            return {'status': 'healthy', 'app': 'medinvest'}, 200
            
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Index route error: {e}")
        # Still return 200 for health checks even on template errors
        if request.headers.get('User-Agent', '').startswith(('GoogleHC', 'kube-probe', 'Cloud-Run')):
            return {'status': 'healthy', 'app': 'medinvest'}, 200
        return f"Application is running. Error: {str(e)}", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        medical_license = request.form['medical_license']
        specialty = request.form['specialty']
        hospital_affiliation = request.form.get('hospital_affiliation', '')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered. Please log in.', 'warning')
            return redirect(url_for('login'))
        
        # Check if medical license is already registered
        existing_license = User.query.filter_by(medical_license=medical_license).first()
        if existing_license:
            flash('Medical license already registered.', 'warning')
            return render_template('register.html')
        
        # Create new user
        user = User()
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.medical_license = medical_license
        user.specialty = specialty
        user.hospital_affiliation = hospital_affiliation
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if user.is_2fa_enabled:
                session['pending_2fa_user_id'] = user.id
                session['next_page'] = request.args.get('next')
                return redirect(url_for('verify_2fa'))
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Social media feed for medical professionals learning investing"""
    try:
        # Get all posts ordered by creation time (optimized with limit)
        feed_posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
        
        # Get suggested users to follow (verified medical professionals) - simplified query
        suggested_users = User.query.filter(
            User.id != current_user.id
        ).limit(3).all()
        
        # Get user stats efficiently
        stats = {
            'posts_count': current_user.posts.count(),
            'followers_count': current_user.followers_count(),
            'following_count': current_user.following_count()
        }
        
        return render_template('dashboard.html', 
                             posts=feed_posts,
                             suggested_users=suggested_users,
                             stats=stats)
    except Exception as e:
        logging.error(f"Dashboard error: {e}")
        # Return simplified dashboard on error
        return render_template('dashboard.html', 
                             posts=[],
                             suggested_users=[],
                             stats={'posts_count': 0, 'followers_count': 0, 'following_count': 0})

@app.route('/modules')
@login_required
def modules():
    category = request.args.get('category', 'all')
    difficulty = request.args.get('difficulty', 'all')
    
    query = Module.query.filter_by(is_published=True)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    if difficulty != 'all':
        query = query.filter_by(difficulty_level=difficulty)
    
    modules = query.order_by(Module.order_index).all()
    
    # Get user progress for each module
    user_progress = {}
    for module in modules:
        progress = UserProgress.query.filter_by(user_id=current_user.id, module_id=module.id).first()
        user_progress[module.id] = progress
    
    categories = db.session.query(Module.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template('modules.html', modules=modules, user_progress=user_progress, 
                         categories=categories, selected_category=category, selected_difficulty=difficulty)

@app.route('/module/<int:module_id>')
@login_required
def module_detail(module_id):
    module = Module.query.get_or_404(module_id)
    
    # Get or create user progress
    progress = UserProgress.query.filter_by(user_id=current_user.id, module_id=module_id).first()
    if not progress:
        progress = UserProgress()
        progress.user_id = current_user.id
        progress.module_id = module_id
        db.session.add(progress)
        db.session.commit()
    
    return render_template('module_detail.html', module=module, progress=progress)

@app.route('/complete_module/<int:module_id>', methods=['POST'])
@login_required
def complete_module(module_id):
    progress = UserProgress.query.filter_by(user_id=current_user.id, module_id=module_id).first()
    if progress:
        progress.completed = True
        progress.completion_date = datetime.utcnow()
        db.session.commit()
        flash('Module completed successfully!', 'success')
    
    return redirect(url_for('modules'))

@app.route('/forums')
@login_required
def forums():
    category = request.args.get('category', 'all')
    
    # Get topics or return empty list if none exist
    try:
        query = ForumTopic.query.filter_by(is_active=True)
        
        if category != 'all':
            query = query.filter_by(category=category)
        
        topics = query.order_by(ForumTopic.created_at.desc()).all()
        
        # Get categories safely
        categories = ['Investment Basics', 'Portfolio Management', 'Healthcare Stocks', 'Market Analysis']
        
    except Exception as e:
        logging.error(f"Error in forums route: {e}")
        topics = []
        categories = ['Investment Basics', 'Portfolio Management', 'Healthcare Stocks']
    
    return render_template('forums.html', topics=topics, categories=categories, selected_category=category)

@app.route('/forum_detail/<int:topic_id>')
@login_required
def forum_detail(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    posts = ForumPost.query.filter_by(topic_id=topic_id, parent_id=None).order_by(ForumPost.created_at.asc()).all()
    
    return render_template('forum_detail.html', topic=topic, posts=posts)

@app.route('/add_post/<int:topic_id>', methods=['POST'])
@login_required
def add_post(topic_id):
    content = request.form['content']
    parent_id = request.form.get('parent_id')
    
    post = ForumPost()
    post.topic_id = topic_id
    post.user_id = current_user.id
    post.content = content
    post.parent_id = int(parent_id) if parent_id else None
    
    db.session.add(post)
    db.session.commit()
    
    flash('Post added successfully!', 'success')
    return redirect(url_for('forum_detail', topic_id=topic_id))

@app.route('/portfolio')
@login_required
def portfolio():
    transactions = PortfolioTransaction.query.filter_by(user_id=current_user.id).order_by(PortfolioTransaction.transaction_date.desc()).all()
    
    # Calculate portfolio summary
    portfolio_summary = {}
    total_value = 0
    
    for transaction in transactions:
        if transaction.symbol not in portfolio_summary:
            portfolio_summary[transaction.symbol] = {'quantity': 0, 'total_cost': 0}
        
        if transaction.transaction_type == 'BUY':
            portfolio_summary[transaction.symbol]['quantity'] += transaction.quantity
            portfolio_summary[transaction.symbol]['total_cost'] += transaction.total_amount
        else:  # SELL
            portfolio_summary[transaction.symbol]['quantity'] -= transaction.quantity
            portfolio_summary[transaction.symbol]['total_cost'] -= transaction.total_amount
    
    return render_template('portfolio.html', transactions=transactions, portfolio_summary=portfolio_summary)

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    symbol = request.form['symbol'].upper()
    transaction_type = request.form['transaction_type']
    quantity = int(request.form['quantity'])
    price = float(request.form['price'])
    
    total_amount = quantity * price
    
    transaction = PortfolioTransaction()
    transaction.user_id = current_user.id
    transaction.symbol = symbol
    transaction.transaction_type = transaction_type
    transaction.quantity = quantity
    transaction.price = price
    transaction.total_amount = total_amount
    
    db.session.add(transaction)
    db.session.commit()
    
    flash(f'Transaction added: {transaction_type} {quantity} shares of {symbol} at ${price:.2f}', 'success')
    return redirect(url_for('portfolio'))

@app.route('/profile')
@login_required
def profile():
    # Get user statistics
    completed_modules = UserProgress.query.filter_by(user_id=current_user.id, completed=True).count()
    total_time_spent = db.session.query(db.func.sum(UserProgress.time_spent)).filter_by(user_id=current_user.id).scalar() or 0
    forum_posts_count = ForumPost.query.filter_by(user_id=current_user.id).count()
    
    # Social media stats
    stats = {
        'posts_count': Post.query.filter_by(author_id=current_user.id).count(),
        'followers_count': Follow.query.filter_by(following_id=current_user.id).count(),
        'following_count': Follow.query.filter_by(follower_id=current_user.id).count(),
        'likes_received': db.session.query(db.func.count(Like.id)).join(Post).filter(Post.author_id == current_user.id).scalar() or 0
    }
    
    return render_template('profile.html', 
                         user=current_user,
                         stats=stats,
                         completed_modules=completed_modules,
                         total_time_spent=total_time_spent,
                         forum_posts_count=forum_posts_count)

def create_sample_data():
    """Create sample data for the application."""
    # Check if sample data already exists
    if Module.query.first():
        return
    
    # Create sample modules
    modules_data = [
        {
            'title': 'Investment Basics for Medical Professionals',
            'description': 'Learn the fundamentals of investing tailored for healthcare professionals',
            'content': '''<h3>Introduction to Investing</h3>
            <p>As a medical professional, you have unique financial considerations and opportunities. This module covers:</p>
            <ul>
                <li>Basic investment principles</li>
                <li>Risk tolerance assessment</li>
                <li>Asset allocation strategies</li>
                <li>Tax considerations for high earners</li>
            </ul>
            <h3>Key Concepts</h3>
            <p>Understanding the time value of money, compound interest, and diversification are crucial foundations for any investment strategy.</p>''',
            'difficulty_level': 'Beginner',
            'estimated_duration': 30,
            'category': 'Fundamentals',
            'order_index': 1
        },
        {
            'title': 'Retirement Planning for Physicians',
            'description': 'Comprehensive retirement planning strategies for medical careers',
            'content': '''<h3>Retirement Planning Essentials</h3>
            <p>Medical professionals face unique retirement challenges including:</p>
            <ul>
                <li>Later career start due to medical training</li>
                <li>High earning potential but also high expenses</li>
                <li>Malpractice insurance considerations</li>
                <li>Practice ownership implications</li>
            </ul>
            <h3>Retirement Vehicles</h3>
            <p>Learn about 401(k), 403(b), IRA, Roth IRA, and specialized plans for medical practices.</p>''',
            'difficulty_level': 'Intermediate',
            'estimated_duration': 45,
            'category': 'Retirement',
            'order_index': 2
        },
        {
            'title': 'Tax-Efficient Investment Strategies',
            'description': 'Optimize your investment returns through tax-efficient strategies',
            'content': '''<h3>Tax Optimization</h3>
            <p>High-earning medical professionals must consider tax implications in all investment decisions:</p>
            <ul>
                <li>Tax-advantaged accounts</li>
                <li>Asset location strategies</li>
                <li>Tax-loss harvesting</li>
                <li>Municipal bonds for high earners</li>
            </ul>
            <h3>Advanced Strategies</h3>
            <p>Explore sophisticated tax planning techniques including backdoor Roth conversions and charitable giving strategies.</p>''',
            'difficulty_level': 'Advanced',
            'estimated_duration': 60,
            'category': 'Tax Planning',
            'order_index': 3
        }
    ]
    
    for module_data in modules_data:
        module = Module(**module_data)
        db.session.add(module)
    
    # Create sample forum topics
    forum_topics = [
        {
            'title': 'Investment Mistakes to Avoid',
            'description': 'Share and discuss common investment mistakes',
            'category': 'General Discussion'
        },
        {
            'title': 'Real Estate vs Stock Market',
            'description': 'Comparing investment in real estate versus stock market',
            'category': 'Investment Strategies'
        },
        {
            'title': 'Emergency Fund Strategies',
            'description': 'How much should physicians keep in emergency funds?',
            'category': 'Financial Planning'
        }
    ]
    
    for topic_data in forum_topics:
        topic = ForumTopic(**topic_data)
        db.session.add(topic)
    
    # Create sample resources
    resources_data = [
        {
            'title': 'Compound Interest Calculator',
            'description': 'Calculate the power of compound interest over time',
            'resource_type': 'Calculator',
            'category': 'Tools',
            'content': 'Interactive calculator for compound interest projections'
        },
        {
            'title': 'Asset Allocation Guide',
            'description': 'Comprehensive guide to asset allocation by age and risk tolerance',
            'resource_type': 'Guide',
            'category': 'Education',
            'content': 'Detailed guide on how to allocate assets across different investment types'
        }
    ]
    
    for resource_data in resources_data:
        resource = Resource(**resource_data)
        db.session.add(resource)
    
    # Create sample social media posts after user creation
    if User.query.count() > 0:
        sample_user = User.query.first()
        
        if sample_user:  # Null check
            # Create sample social media posts  
            sample_social_post = Post()
            sample_social_post.author_id = sample_user.id
            sample_social_post.content = "Just completed the 'Understanding Stock Market Basics' module! The section on healthcare sector investing was particularly insightful. As medical professionals, we have unique insights into which companies are truly innovative. What healthcare stocks are you watching?"
            sample_social_post.post_type = "achievement"
            sample_social_post.tags = "learning, healthcare-stocks, medical-professional"
            db.session.add(sample_social_post)
            
            sample_question_post = Post()
            sample_question_post.author_id = sample_user.id
            sample_question_post.content = "Question for fellow docs: How do you balance investing in individual healthcare stocks vs. broad market ETFs? I'm torn between leveraging our industry knowledge and maintaining diversification."
            sample_question_post.post_type = "question"
            sample_question_post.tags = "investment-strategy, healthcare, diversification"
            db.session.add(sample_question_post)
    
    db.session.commit()
    logging.info("Sample data created successfully")

# Create sample data when the application starts
with app.app_context():
    create_sample_data()


# Social Media Routes
@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    """Create a new social media post"""
    content = request.form.get('content', '').strip()
    post_type = request.form.get('post_type', 'general')
    tags = request.form.get('tags', '')
    is_anonymous = request.form.get('is_anonymous') == '1'
    room_id = request.form.get('room_id', type=int)
    
    if not content:
        flash('Post content cannot be empty.', 'error')
        return redirect(url_for('dashboard'))
    
    post = Post()
    post.author_id = current_user.id
    post.content = content
    post.post_type = post_type
    post.tags = tags
    post.is_anonymous = is_anonymous
    if room_id:
        post.room_id = room_id
    
    # Extract and process hashtags
    import re
    hashtag_pattern = r'#(\w+)'
    found_hashtags = re.findall(hashtag_pattern, content)
    
    try:
        db.session.add(post)
        db.session.flush()
        
        # Create/update hashtags
        for tag_name in found_hashtags[:10]:  # Max 10 hashtags per post
            tag_name_lower = tag_name.lower()
            hashtag = Hashtag.query.filter_by(name=tag_name_lower).first()
            if not hashtag:
                hashtag = Hashtag(name=tag_name_lower)
                db.session.add(hashtag)
                db.session.flush()
            hashtag.post_count = (hashtag.post_count or 0) + 1
            hashtag.weekly_count = (hashtag.weekly_count or 0) + 1
            hashtag.last_used = datetime.utcnow()
            
            post_hashtag = PostHashtag(post_id=post.id, hashtag_id=hashtag.id)
            db.session.add(post_hashtag)
        
        # Update room post count if posting to a room
        if room_id:
            room = InvestmentRoom.query.get(room_id)
            if room:
                room.post_count = (room.post_count or 0) + 1
        
        db.session.commit()
        flash('Post created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating post: {e}")
        flash('Error creating post. Please try again.', 'error')
    
    # Redirect back to room if posting from a room
    if room_id:
        return redirect(url_for('room_detail', room_id=room_id))
    return redirect(url_for('dashboard'))


@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    """Like or unlike a post"""
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if existing_like:
        # Unlike the post
        db.session.delete(existing_like)
        action = 'unliked'
    else:
        # Like the post
        like = Like()
        like.user_id = current_user.id
        like.post_id = post_id
        db.session.add(like)
        action = 'liked'
        
        # Create notification if it's not the user's own post
        if post.author_id != current_user.id:
            notification = Notification()
            notification.recipient_id = post.author_id
            notification.sender_id = current_user.id
            notification.notification_type = 'like'
            notification.message = f'{current_user.full_name} liked your post'
            notification.related_post_id = post_id
            db.session.add(notification)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'action': action,
            'likes_count': post.likes_count()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error liking post: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/comment_post/<int:post_id>', methods=['POST'])
@login_required
def comment_post(post_id):
    """Add a comment to a post"""
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('dashboard'))
    
    comment = Comment()
    comment.post_id = post_id
    comment.author_id = current_user.id
    comment.content = content
    
    # Create notification if it's not the user's own post
    if post.author_id != current_user.id:
        notification = Notification()
        notification.recipient_id = post.author_id
        notification.sender_id = current_user.id
        notification.notification_type = 'comment'
        notification.message = f'{current_user.full_name} commented on your post'
        notification.related_post_id = post_id
        db.session.add(notification)
    
    try:
        db.session.add(comment)
        db.session.commit()
        flash('Comment added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding comment: {e}")
        flash('Error adding comment. Please try again.', 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/follow_user/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    """Follow or unfollow a user"""
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot follow yourself'}), 400
    
    user = User.query.get_or_404(user_id)
    
    if current_user.is_following(user):
        # Unfollow
        current_user.unfollow(user)
        action = 'unfollowed'
    else:
        # Follow
        current_user.follow(user)
        action = 'followed'
        
        # Create notification
        notification = Notification()
        notification.recipient_id = user_id
        notification.sender_id = current_user.id
        notification.notification_type = 'follow'
        notification.message = f'{current_user.full_name} started following you'
        db.session.add(notification)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'action': action,
            'followers_count': user.followers_count()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error following user: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id):
    """View user profile"""
    user = User.query.get_or_404(user_id)
    posts = user.posts.order_by(Post.created_at.desc()).limit(20).all()
    
    # Get user stats
    stats = {
        'posts_count': user.posts.count(),
        'followers_count': user.followers_count(),
        'following_count': user.following_count(),
        'is_following': current_user.is_following(user) if user != current_user else False
    }
    
    return render_template('profile.html', user=user, posts=posts, stats=stats)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '')
        current_user.location = request.form.get('location', '')
        current_user.years_of_experience = request.form.get('years_of_experience', type=int)
        current_user.investment_interests = request.form.get('investment_interests', '')
        current_user.hospital_affiliation = request.form.get('hospital_affiliation', '')
        
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_profile', user_id=current_user.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating profile: {e}")
            flash('Error updating profile. Please try again.', 'error')
    
    return render_template('edit_profile.html', user=current_user)


@app.route('/notifications')
@login_required
def notifications():
    """View user notifications"""
    notifications = Notification.query.filter_by(
        recipient_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    # Mark notifications as read
    unread_notifications = Notification.query.filter_by(
        recipient_id=current_user.id, 
        is_read=False
    ).all()
    
    for notification in unread_notifications:
        notification.is_read = True
    
    try:
        db.session.commit()
    except Exception as e:
        logging.error(f"Error marking notifications as read: {e}")
    
    return render_template('notifications.html', notifications=notifications)


# Two-Factor Authentication Routes
@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    """Verify 2FA code during login"""
    if 'pending_2fa_user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        user = User.query.get(session['pending_2fa_user_id'])
        
        if user and user.verify_totp(code):
            login_user(user)
            next_page = session.pop('next_page', None)
            session.pop('pending_2fa_user_id', None)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    return render_template('verify_2fa.html')


@app.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Setup 2FA for the current user"""
    if current_user.is_2fa_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('security_settings'))
    
    if request.method == 'POST':
        return redirect(url_for('confirm_2fa'))
    
    if not current_user.totp_secret:
        current_user.generate_totp_secret()
        db.session.commit()
    
    totp_uri = current_user.get_totp_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('setup_2fa.html', 
                         qr_code=qr_code_base64, 
                         secret=current_user.totp_secret)


@app.route('/confirm-2fa', methods=['GET', 'POST'])
@login_required
def confirm_2fa():
    """Confirm 2FA setup with a verification code"""
    if current_user.is_2fa_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('security_settings'))
    
    if not current_user.totp_secret:
        return redirect(url_for('setup_2fa'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if current_user.verify_totp(code):
            current_user.is_2fa_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled successfully!', 'success')
            return redirect(url_for('security_settings'))
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    return render_template('confirm_2fa.html')


@app.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA for the current user"""
    password = request.form.get('password', '')
    
    if not current_user.check_password(password):
        flash('Invalid password. Please try again.', 'error')
        return redirect(url_for('security_settings'))
    
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('security_settings'))


@app.route('/security-settings')
@login_required
def security_settings():
    """Security settings page"""
    return render_template('security_settings.html')


# Password Reset Routes
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.generate_password_reset_token()
            db.session.commit()
            
            reset_url = url_for('reset_password', token=token, _external=True)
            send_password_reset_email(user, reset_url)
            
            logging.info(f"Password reset requested for {email}")
        
        flash('If an account with that email exists, you will receive password reset instructions.', 'info')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)
        
        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        
        flash('Your password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

# ----------------------
# Doctor trust & verification (NPI-based)
# ----------------------

@app.route('/api/verification/submit', methods=['POST'])
@login_required
def api_verification_submit():
    data = request.get_json(silent=True) or {}
    npi_number = (data.get('npi_number') or '').strip() or None
    license_state = (data.get('license_state') or '').strip().upper() or None

    if not npi_number or not npi_number.isdigit() or len(npi_number) not in (10, 11, 12):
        return jsonify({'error': 'invalid_npi_number'}), 400
    if license_state and len(license_state) != 2:
        return jsonify({'error': 'invalid_license_state'}), 400

    current_user.npi_number = npi_number
    current_user.license_state = license_state
    current_user.verification_status = 'pending'
    current_user.verification_submitted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'status': 'submitted', 'verification_status': current_user.verification_status}), 200


# ----------------------
# Doctor-only groups (community graph)
# ----------------------

@app.route('/api/groups', methods=['GET', 'POST'])
@login_required
def api_groups():
    if request.method == 'GET':
        groups = Group.query.order_by(Group.created_at.desc()).limit(50).all()
        return jsonify({'groups': [
            {
                'id': g.id,
                'name': g.name,
                'description': g.description,
                'privacy': g.privacy,
                'created_at': g.created_at.isoformat(),
            }
            for g in groups
        ]})

    # POST: create
    if not (getattr(current_user, 'verification_status', 'unverified') == 'verified' or getattr(current_user, 'is_verified', False)):
        return jsonify({'error': 'verification_required'}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip() or None
    privacy = (data.get('privacy') or 'private').strip().lower()
    if privacy not in ('public', 'private', 'hidden'):
        return jsonify({'error': 'invalid_privacy'}), 400
    if not name or len(name) < 3:
        return jsonify({'error': 'invalid_name'}), 400

    g = Group(name=name, description=description, privacy=privacy, created_by_id=current_user.id)
    db.session.add(g)
    db.session.flush()

    # creator becomes admin member
    gm = GroupMembership(group_id=g.id, user_id=current_user.id, role='admin', status='active')
    db.session.add(gm)
    db.session.commit()

    return jsonify({'status': 'created', 'group': {'id': g.id, 'name': g.name}}), 201


@app.route('/api/groups/<int:group_id>/join', methods=['POST'])
@login_required
@require_verified
def api_group_join(group_id: int):
    g = Group.query.get_or_404(group_id)
    existing = GroupMembership.query.filter_by(group_id=g.id, user_id=current_user.id).first()
    if existing:
        return jsonify({'status': 'already_member', 'membership_status': existing.status}), 200

    gm = GroupMembership(group_id=g.id, user_id=current_user.id, role='member', status='active')
    db.session.add(gm)
    db.session.commit()
    return jsonify({'status': 'joined', 'group_id': g.id}), 200


@app.route('/api/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def api_group_leave(group_id: int):
    gm = GroupMembership.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not gm:
        return jsonify({'status': 'not_member'}), 200
    db.session.delete(gm)
    db.session.commit()
    return jsonify({'status': 'left', 'group_id': group_id}), 200


# ----------------------
# AI endpoints (summaries + deal analysis)
# ----------------------

@app.route('/api/ai/summarize', methods=['POST'])
@login_required
@require_verified
def api_ai_summarize():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'missing_text'}), 400
    return jsonify(summarize_text(text)), 200


@app.route('/api/ai/deal-analyze', methods=['POST'])
@login_required
@require_verified
def api_ai_deal_analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'missing_text'}), 400
    return jsonify(analyze_deal(text)), 200


# ----------------------
# Admin Verification Endpoints
# ----------------------

@app.route('/api/admin/verification/pending')
@login_required
def api_admin_verification_pending():
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    limit = request.args.get('limit', 25, type=int)
    offset = request.args.get('offset', 0, type=int)
    search = request.args.get('search', '', type=str).strip()
    
    q = User.query.filter(User.verification_status == 'pending')
    
    if search:
        search_pattern = f"%{search}%"
        q = q.filter(
            db.or_(
                (User.first_name + ' ' + User.last_name).ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.npi_number.ilike(search_pattern)
            )
        )
    
    total = q.count()
    users = q.order_by(User.verification_submitted_at.asc()).limit(limit).offset(offset).all()
    
    return jsonify({
        'total': total,
        'results': [
            {
                'user_id': u.id,
                'full_name': u.full_name,
                'email': u.email,
                'npi_number': u.npi_number,
                'license_state': u.license_state,
                'specialty': u.specialty,
                'submitted_at': u.verification_submitted_at.isoformat() if u.verification_submitted_at else None
            }
            for u in users
        ]
    })


@app.route('/api/admin/verification/<int:user_id>')
@login_required
def api_admin_verification_detail(user_id: int):
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    user = User.query.get_or_404(user_id)
    return jsonify({
        'user_id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'specialty': user.specialty,
        'npi_number': user.npi_number,
        'license_state': user.license_state,
        'medical_license': user.medical_license,
        'hospital_affiliation': user.hospital_affiliation,
        'verification_status': user.verification_status,
        'verification_notes': user.verification_notes,
        'submitted_at': user.verification_submitted_at.isoformat() if user.verification_submitted_at else None,
        'created_at': user.created_at.isoformat() if user.created_at else None
    })


@app.route('/api/admin/verification/<int:user_id>/approve', methods=['POST'])
@login_required
def api_admin_verification_approve(user_id: int):
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    user = User.query.get_or_404(user_id)
    user.verification_status = 'verified'
    user.is_verified = True
    user.verified_at = datetime.utcnow()
    db.session.commit()
    
    next_user = User.query.filter(
        User.verification_status == 'pending',
        User.id != user_id
    ).order_by(User.verification_submitted_at.asc()).first()
    
    return jsonify({
        'status': 'approved',
        'user_id': user_id,
        'next_user_id': next_user.id if next_user else None
    })


@app.route('/api/admin/verification/<int:user_id>/reject', methods=['POST'])
@login_required
def api_admin_verification_reject(user_id: int):
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json(silent=True) or {}
    notes = (data.get('notes') or '').strip()
    
    user = User.query.get_or_404(user_id)
    user.verification_status = 'rejected'
    user.is_verified = False
    user.verification_notes = notes or user.verification_notes
    db.session.commit()
    
    next_user = User.query.filter(
        User.verification_status == 'pending',
        User.id != user_id
    ).order_by(User.verification_submitted_at.asc()).first()
    
    return jsonify({
        'status': 'rejected',
        'user_id': user_id,
        'next_user_id': next_user.id if next_user else None
    })


# Admin verification UI routes
@app.route('/admin/verification')
@login_required
def admin_verification_list():
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    pending_users = User.query.filter(User.verification_status == 'pending').order_by(User.verification_submitted_at.asc()).all()
    return render_template('admin/verification_list.html', pending_users=pending_users)


@app.route('/admin/verification/<int:user_id>')
@login_required
def admin_verification_review(user_id: int):
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    return render_template('admin/verification_review.html', user=user)


# ----------------------
# AI Jobs API Endpoints
# ----------------------

@app.route('/api/ai/jobs', methods=['POST'])
@login_required
@require_verified
def api_ai_jobs_create():
    data = request.get_json(silent=True) or {}
    job_type = (data.get('job_type') or '').strip()
    deal_id = data.get('deal_id')
    post_id = data.get('post_id')
    input_text = (data.get('input_text') or '').strip() or None
    idempotency_key = request.headers.get('Idempotency-Key', '').strip() or None
    
    if job_type not in ('summarize_thread', 'analyze_deal'):
        return jsonify({'error': 'invalid_job_type'}), 400
    
    if job_type == 'analyze_deal' and not deal_id:
        return jsonify({'error': 'deal_id_required'}), 400
    
    try:
        job = enqueue_ai_job(
            job_type=job_type,
            created_by_id=current_user.id,
            input_text=input_text,
            post_id=post_id,
            deal_id=deal_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as e:
        if str(e) == 'rate_limited':
            return jsonify({'error': 'rate_limited', 'message': 'Too many AI requests. Please wait and try again.'}), 429
        raise
    
    reused = getattr(job, '_reused', False)
    return jsonify({'job_id': job.id, 'status': job.status, 'reused': reused}), 200 if reused else 201


@app.route('/api/ai/jobs/<int:job_id>')
@login_required
def api_ai_jobs_status(job_id: int):
    job = AiJob.query.get_or_404(job_id)
    
    is_admin = getattr(current_user, 'role', '') == 'admin'
    if job.created_by_id != current_user.id and not is_admin:
        return jsonify({'error': 'forbidden'}), 403
    
    result_ref = None
    if job.status == 'done':
        if job.deal_id:
            analysis = DealAnalysis.query.filter_by(deal_id=job.deal_id).order_by(DealAnalysis.created_at.desc()).first()
            if analysis:
                result_ref = {'deal_analysis_id': analysis.id}
    
    return jsonify({
        'job_id': job.id,
        'status': job.status,
        'job_type': job.job_type,
        'error': job.error,
        'result_ref': result_ref,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None
    })


@app.route('/api/ai/jobs/<int:job_id>/run', methods=['POST'])
@login_required
def api_ai_jobs_run(job_id: int):
    decision = can(current_user, Actions.ADMIN_REVIEW_VERIFICATION, None)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    job = process_job(job_id)
    return jsonify({'job_id': job.id, 'status': job.status, 'error': job.error})


# ----------------------
# Deals API Endpoints
# ----------------------

@app.route('/api/deals/<int:deal_id>')
@login_required
@require_verified
def api_deal_detail(deal_id: int):
    deal = DealDetails.query.get_or_404(deal_id)
    post = Post.query.get(deal.post_id) if deal.post_id else None
    
    analyses_query = DealAnalysis.query.filter_by(deal_id=deal.id).order_by(DealAnalysis.created_at.desc()).limit(10).all()
    analyses = [
        {
            'id': a.id,
            'summary': a.output_text,
            'provider': a.provider,
            'model': a.model,
            'created_at': a.created_at.isoformat() if a.created_at else None
        }
        for a in analyses_query
    ]
    
    return jsonify({
        'deal': {
            'id': deal.id,
            'post_id': deal.post_id,
            'asset_class': deal.asset_class,
            'strategy': deal.strategy,
            'location': deal.location,
            'time_horizon_months': deal.time_horizon_months,
            'target_irr': deal.target_irr,
            'target_multiple': deal.target_multiple,
            'minimum_investment': deal.minimum_investment,
            'sponsor_name': deal.sponsor_name,
            'sponsor_track_record': deal.sponsor_track_record,
            'thesis': deal.thesis,
            'key_risks': deal.key_risks,
            'diligence_needed': deal.diligence_needed,
            'status': deal.status,
            'created_at': deal.created_at.isoformat() if deal.created_at else None,
            'post_content': post.content if post else None
        },
        'analyses': analyses
    })


# ----------------------
# First-Deal Wizard
# ----------------------

ASSET_CLASSES = [
    'Multifamily',
    'Self-Storage',
    'Medical Office',
    'Industrial',
    'Retail',
    'Private Equity',
    'Venture Capital',
    'Syndication',
    'REIT',
    'Crypto/Web3',
    'Other',
]


@app.route('/deals/new')
@login_required
@require_verified
def deal_wizard():
    return render_template('deal_wizard.html', asset_classes=ASSET_CLASSES)


@app.route('/deals/new', methods=['POST'])
@login_required
@require_verified
def deal_wizard_submit():
    asset_class = request.form.get('asset_class', '').strip()
    thesis = request.form.get('thesis', '').strip()
    feedback_areas = request.form.getlist('feedback_areas')
    feedback_request = request.form.get('feedback_request', '').strip()
    visibility = request.form.get('visibility', 'physicians')
    disclaimer_accepted = request.form.get('disclaimer_accepted') == 'yes'
    
    if not asset_class or not thesis:
        flash('Please complete all required fields.', 'warning')
        return redirect(url_for('deal_wizard'))
    
    if not disclaimer_accepted:
        flash('You must acknowledge the disclaimer to share a deal.', 'warning')
        return redirect(url_for('deal_wizard'))
    
    if len(feedback_areas) > 3:
        flash('Please select up to 3 feedback areas only.', 'warning')
        return redirect(url_for('deal_wizard'))
    
    post_content = f"**New Deal: {asset_class}**\n\n{thesis}"
    if feedback_areas:
        area_labels = {'returns': 'Return expectations', 'sponsor': 'Sponsor experience', 
                       'diligence': 'Due diligence', 'market': 'Market conditions',
                       'risks': 'Key risks', 'structure': 'Deal structure'}
        areas_text = ', '.join(area_labels.get(a, a) for a in feedback_areas[:3])
        post_content += f"\n\n**Looking for feedback on:** {areas_text}"
    if feedback_request:
        post_content += f"\n\n**Additional context:** {feedback_request}"
    
    post = Post()
    post.author_id = current_user.id
    post.content = post_content
    post.post_type = 'deal'
    post.visibility = visibility
    post.tags = asset_class.lower().replace(' ', '-')
    db.session.add(post)
    db.session.flush()
    
    deal = DealDetails(
        post_id=post.id,
        asset_class=asset_class,
        thesis=thesis,
        diligence_needed=feedback_request or None,
        feedback_areas=','.join(feedback_areas) if feedback_areas else None,
        disclaimer_acknowledged=True,
        status='open'
    )
    db.session.add(deal)
    db.session.commit()
    
    try:
        job = enqueue_ai_job(
            job_type='analyze_deal',
            created_by_id=current_user.id,
            deal_id=deal.id,
        )
        logging.info(f"Auto-enqueued AI job {job.id} for deal {deal.id}")
    except ValueError as e:
        if str(e) == 'rate_limited':
            flash('AI analysis queued but rate limited. Will run shortly.', 'info')
        else:
            logging.error(f"Failed to enqueue AI job: {e}")
    
    _notify_relevant_physicians(deal, post)
    
    flash('Deal shared! AI Analyst is reviewing it now.', 'success')
    return redirect(url_for('view_post', post_id=post.id))


def _notify_relevant_physicians(deal: DealDetails, post: Post):
    """Notify physicians with matching investment interests or specialties."""
    try:
        asset_class_lower = deal.asset_class.lower()
        
        relevant_users = User.query.filter(
            User.id != current_user.id,
            User.verification_status == 'verified',
            db.or_(
                User.investment_interests.ilike(f'%{asset_class_lower}%'),
                User.specialty.in_(['General Practice', 'Internal Medicine', 'Surgery'])
            )
        ).limit(10).all()
        
        for user in relevant_users:
            notification = Notification(
                recipient_id=user.id,
                sender_id=current_user.id,
                notification_type='new_deal',
                message=f'New {deal.asset_class} deal needs eyes',
                related_post_id=post.id,
                is_read=False,
            )
            db.session.add(notification)
        
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to notify physicians: {e}")


# Signal score functions

def _exp_decay(age_days: float, halflife_days: float = 7.0) -> float:
    return math.exp(-age_days / max(halflife_days, 0.1))


def compute_deal_signal_score(deal: DealDetails) -> float:
    post = Post.query.get(deal.post_id)
    endorsements = ReputationEvent.query.filter_by(related_post_id=deal.post_id, event_type='post_upvote').count()
    comment_count = Comment.query.filter_by(post_id=deal.post_id).count()
    author_rep = 0
    if post and post.author:
        author_rep = int(post.author.reputation_score or 0)
    age_days = 0.0
    if deal.created_at:
        age_days = (datetime.utcnow() - deal.created_at).total_seconds() / 86400.0
    score = (10.0 * endorsements) + (2.0 * comment_count) + (0.1 * author_rep)
    return float(score) * _exp_decay(age_days, 7.0)


def compute_comment_impact_score(c: Comment) -> float:
    endorsements = ReputationEvent.query.filter_by(related_post_id=c.post_id, event_type='comment_upvote').count()
    author_rep = int(c.author.reputation_score or 0) if c.author else 0
    age_days = 0.0
    if c.created_at:
        age_days = (datetime.utcnow() - c.created_at).total_seconds() / 86400.0
    score = (5.0 * endorsements) + (3.0 * math.log1p(max(author_rep, 0)))
    return float(score) * _exp_decay(age_days, 7.0)


# Deals API

@app.route('/api/deals', methods=['GET', 'POST'])
@login_required
@require_verified
def api_deals():
    if request.method == 'GET':
        asset_class = (request.args.get('asset_class') or '').strip() or None
        status = (request.args.get('status') or '').strip() or None
        sort = (request.args.get('sort') or '').strip() or 'new'

        q = DealDetails.query
        if sort == 'trending':
            deals = q.all()
            scored = [(d, compute_deal_signal_score(d)) for d in deals]
            scored.sort(key=lambda x: x[1], reverse=True)
            offset = int(request.args.get('offset') or 0)
            limit = int(request.args.get('limit') or 25)
            scored_page = scored[offset:offset+limit]
            return jsonify({'results': [
                {
                    'id': d.id,
                    'post_id': d.post_id,
                    'asset_class': d.asset_class,
                    'strategy': d.strategy,
                    'location': d.location,
                    'time_horizon_months': d.time_horizon_months,
                    'thesis': d.thesis,
                    'status': d.status,
                    'created_at': d.created_at.isoformat() if d.created_at else None,
                    'signal_score': s,
                } for d, s in scored_page
            ]}), 200

        if asset_class:
            q = q.filter(DealDetails.asset_class == asset_class)
        if status:
            q = q.filter(DealDetails.status == status)
        deals = q.order_by(DealDetails.created_at.desc()).limit(50).all()

        out = []
        for d in deals:
            p = Post.query.get(d.post_id) if d.post_id else None
            out.append({
                'deal_id': d.id,
                'post_id': d.post_id,
                'asset_class': d.asset_class,
                'strategy': d.strategy,
                'location': d.location,
                'time_horizon_months': d.time_horizon_months,
                'target_irr': d.target_irr,
                'target_multiple': d.target_multiple,
                'minimum_investment': d.minimum_investment,
                'sponsor_name': d.sponsor_name,
                'status': d.status,
                'thesis': d.thesis,
                'post_content': (p.content if p else None),
                'created_at': d.created_at.isoformat() if d.created_at else None,
            })
        return jsonify({'deals': out}), 200

    data = request.get_json(silent=True) or {}
    asset_class = (data.get('asset_class') or '').strip()
    thesis = (data.get('thesis') or '').strip()
    post_content = (data.get('post_content') or '').strip() or thesis

    if not asset_class:
        return jsonify({'error': 'missing_asset_class'}), 400
    if not thesis:
        return jsonify({'error': 'missing_thesis'}), 400

    strategy = (data.get('strategy') or '').strip() or None
    location = (data.get('location') or '').strip() or None
    sponsor_name = (data.get('sponsor_name') or '').strip() or None
    sponsor_track_record = (data.get('sponsor_track_record') or '').strip() or None
    key_risks = (data.get('key_risks') or '').strip() or None
    diligence_needed = (data.get('diligence_needed') or '').strip() or None
    status = (data.get('status') or 'open').strip().lower()
    if status not in ('open', 'closed', 'pass'):
        return jsonify({'error': 'invalid_status'}), 400

    def _to_int(v):
        try:
            return int(v) if v is not None and v != '' else None
        except Exception:
            return None

    def _to_float(v):
        try:
            return float(v) if v is not None and v != '' else None
        except Exception:
            return None

    time_horizon_months = _to_int(data.get('time_horizon_months'))
    minimum_investment = _to_int(data.get('minimum_investment'))
    target_irr = _to_float(data.get('target_irr'))
    target_multiple = _to_float(data.get('target_multiple'))

    post = Post(
        author_id=current_user.id,
        content=post_content,
        post_type='deal',
        visibility=(data.get('visibility') or 'physicians'),
        group_id=data.get('group_id') or None,
    )
    db.session.add(post)
    db.session.flush()

    deal = DealDetails(
        post_id=post.id,
        asset_class=asset_class,
        strategy=strategy,
        location=location,
        time_horizon_months=time_horizon_months,
        target_irr=target_irr,
        target_multiple=target_multiple,
        minimum_investment=minimum_investment,
        sponsor_name=sponsor_name,
        sponsor_track_record=sponsor_track_record,
        thesis=thesis,
        key_risks=key_risks,
        diligence_needed=diligence_needed,
        status=status,
    )
    db.session.add(deal)
    db.session.commit()
    return jsonify({'status': 'created', 'deal_id': deal.id, 'post_id': post.id}), 201


@app.route('/api/deals/<int:deal_id>', methods=['GET'])
@login_required
@require_verified
def api_deal_get(deal_id: int):
    deal = DealDetails.query.get_or_404(deal_id)
    post = Post.query.get(deal.post_id) if deal.post_id else None
    analyses = DealAnalysis.query.filter_by(deal_id=deal.id).order_by(DealAnalysis.created_at.desc()).limit(10).all()
    return jsonify({
        'deal': {
            'id': deal.id,
            'post_id': deal.post_id,
            'asset_class': deal.asset_class,
            'strategy': deal.strategy,
            'location': deal.location,
            'time_horizon_months': deal.time_horizon_months,
            'target_irr': deal.target_irr,
            'target_multiple': deal.target_multiple,
            'minimum_investment': deal.minimum_investment,
            'sponsor_name': deal.sponsor_name,
            'sponsor_track_record': deal.sponsor_track_record,
            'thesis': deal.thesis,
            'key_risks': deal.key_risks,
            'diligence_needed': deal.diligence_needed,
            'status': deal.status,
            'created_at': deal.created_at.isoformat() if deal.created_at else None,
        },
        'post': {
            'id': post.id if post else None,
            'content': post.content if post else None,
            'author_id': post.author_id if post else None,
            'created_at': post.created_at.isoformat() if post and post.created_at else None,
        },
        'analyses': [
            {
                'id': a.id,
                'provider': a.provider,
                'model': a.model,
                'output_text': a.output_text,
                'created_at': a.created_at.isoformat() if a.created_at else None,
            } for a in analyses
        ]
    }), 200


# Invites API

@app.route('/api/invites', methods=['GET', 'POST'])
@login_required
@require_verified
def api_invites():
    if request.method == 'GET':
        invites = Invite.query.filter_by(inviter_user_id=current_user.id).order_by(Invite.created_at.desc()).limit(200).all()
        return jsonify({
            'invite_credits': int(getattr(current_user, 'invite_credits', 0) or 0),
            'results': [{
                'id': i.id,
                'code': i.code,
                'invitee_email': i.invitee_email,
                'status': i.status,
                'created_at': i.created_at.isoformat() if i.created_at else None,
                'expires_at': i.expires_at.isoformat() if i.expires_at else None,
                'accepted_at': i.accepted_at.isoformat() if i.accepted_at else None,
            } for i in invites]
        }), 200

    if (current_user.invite_credits or 0) <= 0 and (current_user.role != 'admin'):
        return jsonify({'error': 'no_invites_remaining'}), 403

    data = request.get_json(silent=True) or {}
    invitee_email = (data.get('invitee_email') or '').strip() or None

    i = Invite(
        code=Invite.new_code(),
        inviter_user_id=current_user.id,
        invitee_email=invitee_email,
        status='issued',
        expires_at=datetime.utcnow() + timedelta(days=14),
    )
    db.session.add(i)
    if current_user.role != 'admin':
        current_user.invite_credits = (current_user.invite_credits or 0) - 1
    db.session.commit()

    return jsonify({
        'id': i.id,
        'code': i.code,
        'invitee_email': i.invitee_email,
        'status': i.status,
        'expires_at': i.expires_at.isoformat() if i.expires_at else None,
        'invite_credits': int(current_user.invite_credits or 0),
    }), 201


@app.route('/api/invites/accept', methods=['POST'])
def api_invites_accept():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip().upper()
    if not code:
        return jsonify({'error': 'missing_code'}), 400

    inv = Invite.query.filter_by(code=code).first()
    if not inv:
        return jsonify({'error': 'invalid_code'}), 404
    if inv.status != 'issued':
        return jsonify({'error': 'invite_not_active', 'status': inv.status}), 400
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return jsonify({'error': 'invite_expired'}), 400

    inv.status = 'accepted'
    inv.accepted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'invite_id': inv.id}), 200


# Digests API

def generate_weekly_digest(period_days: int = 7) -> Digest:
    end = datetime.utcnow()
    start = end - timedelta(days=period_days)

    deals = DealDetails.query.filter(DealDetails.created_at >= start).all()
    deal_scored = [(d, compute_deal_signal_score(d)) for d in deals]
    deal_scored.sort(key=lambda x: x[1], reverse=True)
    top_deals = deal_scored[:3]

    comments = Comment.query.filter(Comment.created_at >= start).all()
    comment_scored = [(c, compute_comment_impact_score(c)) for c in comments]
    comment_scored.sort(key=lambda x: x[1], reverse=True)
    top_comments = comment_scored[:3]

    digest = Digest(period_start=start, period_end=end)
    db.session.add(digest)
    db.session.flush()

    rank = 1
    for d, s in top_deals:
        db.session.add(DigestItem(digest_id=digest.id, item_type='deal', entity_id=d.id, score=s, rank=rank))
        rank += 1

    rank = 1
    for c, s in top_comments:
        db.session.add(DigestItem(digest_id=digest.id, item_type='comment', entity_id=c.id, score=s, rank=rank))
        rank += 1

    summary_payload = {
        "summary": "Top deals and discussions from the past week. Open the digest to review details.",
    }
    db.session.add(DigestItem(digest_id=digest.id, item_type='summary', entity_id=None, score=0.0, rank=1, payload_json=json.dumps(summary_payload)))

    db.session.commit()
    return digest


@app.route('/api/digests/latest', methods=['GET'])
@login_required
@require_verified
def api_digest_latest():
    d = Digest.query.order_by(Digest.created_at.desc()).first()
    if not d:
        return jsonify({'error': 'no_digest'}), 404
    return api_digest_get(d.id)


@app.route('/api/digests/<int:digest_id>', methods=['GET'])
@login_required
@require_verified
def api_digest_get(digest_id: int):
    d = Digest.query.get_or_404(digest_id)
    items = DigestItem.query.filter_by(digest_id=d.id).order_by(DigestItem.item_type.asc(), DigestItem.rank.asc()).all()
    return jsonify({
        'digest': {
            'id': d.id,
            'period_start': d.period_start.isoformat() if d.period_start else None,
            'period_end': d.period_end.isoformat() if d.period_end else None,
            'created_at': d.created_at.isoformat() if d.created_at else None,
        },
        'items': [{
            'id': it.id,
            'item_type': it.item_type,
            'entity_id': it.entity_id,
            'score': it.score,
            'rank': it.rank,
            'payload': json.loads(it.payload_json) if it.payload_json else None,
            'created_at': it.created_at.isoformat() if it.created_at else None,
        } for it in items]
    }), 200


# Analytics Dashboard (Admin-only)

@app.route('/admin/analytics')
@login_required
@require_roles('admin')
def admin_analytics():
    return render_template('admin_analytics.html')


@app.route('/api/admin/analytics/overview', methods=['GET'])
@login_required
@require_roles('admin')
def api_admin_analytics_overview():
    from sqlalchemy import text
    
    now = datetime.utcnow()
    window_start = now - timedelta(days=7)

    # 1) Verified WAU - unique verified physicians active in last 7 days
    # Active = post, comment, or last_seen
    verified_wau_result = db.session.execute(text("""
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        LEFT JOIN posts p ON p.author_id = u.id AND p.created_at >= :start
        LEFT JOIN comments c ON c.author_id = u.id AND c.created_at >= :start
        WHERE u.verification_status = 'verified'
          AND (
            u.last_seen >= :start
            OR p.id IS NOT NULL
            OR c.id IS NOT NULL
          )
    """), {"start": window_start})
    verified_wau = verified_wau_result.scalar() or 0

    # 2) Deal WAU - verified physicians who created or commented on a deal in last 7 days
    deal_wau_result = db.session.execute(text("""
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        LEFT JOIN posts p ON p.author_id = u.id AND p.post_type = 'deal' AND p.created_at >= :start
        LEFT JOIN comments c ON c.author_id = u.id AND c.created_at >= :start
        LEFT JOIN posts cp ON cp.id = c.post_id AND cp.post_type = 'deal'
        WHERE u.verification_status = 'verified'
          AND (
            p.id IS NOT NULL
            OR cp.id IS NOT NULL
          )
    """), {"start": window_start})
    deal_wau = deal_wau_result.scalar() or 0

    # 3) Time to First Value (p50) - median hours from verified_at to first post/comment
    ttfv_result = db.session.execute(text("""
        SELECT
          PERCENTILE_CONT(0.5)
          WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (first_action_at - verified_at))/3600)
        FROM (
          SELECT
            u.id,
            u.verified_at,
            LEAST(
              MIN(p.created_at),
              MIN(c.created_at)
            ) AS first_action_at
          FROM users u
          LEFT JOIN posts p ON p.author_id = u.id
          LEFT JOIN comments c ON c.author_id = u.id
          WHERE u.verified_at IS NOT NULL
          GROUP BY u.id, u.verified_at
        ) t
        WHERE first_action_at IS NOT NULL
          AND first_action_at > verified_at
    """))
    ttfv = ttfv_result.scalar() or 0

    # 4) Verification SLA p50 / p95 - hours from submission to approval
    sla_result = db.session.execute(text("""
        SELECT
          PERCENTILE_CONT(0.5)
            WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (verified_at - verification_submitted_at))/3600) AS p50,
          PERCENTILE_CONT(0.95)
            WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (verified_at - verification_submitted_at))/3600) AS p95
        FROM users
        WHERE verified_at IS NOT NULL
          AND verification_submitted_at IS NOT NULL
    """))
    sla = sla_result.fetchone()
    sla_p50 = float(sla.p50 or 0) if sla and sla.p50 else 0
    sla_p95 = float(sla.p95 or 0) if sla and sla.p95 else 0

    # 5) Invites 7d - issued vs accepted with conversion
    invites_result = db.session.execute(text("""
        SELECT
          COUNT(*) FILTER (WHERE status IN ('issued','accepted')) AS issued,
          COUNT(*) FILTER (WHERE status = 'accepted') AS accepted
        FROM invites
        WHERE created_at >= :start
    """), {"start": window_start})
    invites = invites_result.fetchone()
    invites_issued = int(invites.issued or 0) if invites else 0
    invites_accepted = int(invites.accepted or 0) if invites else 0
    conversion_pct = round((invites_accepted / invites_issued * 100) if invites_issued else 0, 1)

    return jsonify({
        'verified_wau': verified_wau,
        'deal_wau': deal_wau,
        'time_to_first_value_hours_p50': round(float(ttfv), 1),
        'verification_sla_hours': {
            'p50': round(sla_p50, 1),
            'p95': round(sla_p95, 1)
        },
        'invites_7d': {
            'issued': invites_issued,
            'accepted': invites_accepted,
            'conversion_pct': conversion_pct
        },
        'window': {
            'start': window_start.isoformat() + 'Z',
            'end': now.isoformat() + 'Z'
        }
    }), 200


@app.route('/api/admin/analytics/cohorts', methods=['GET'])
@login_required
@require_roles('admin')
def api_admin_analytics_cohorts():
    """Per-cohort analytics by invite_source, specialty, or verification_week."""
    from sqlalchemy import text
    
    dimension = request.args.get('dimension', 'specialty')
    metric = request.args.get('metric', 'activation')
    window_days = int(request.args.get('window_days', 7))
    
    now = datetime.utcnow()
    window_start = now - timedelta(days=window_days)
    
    if dimension not in ('invite_source', 'specialty', 'verification_week'):
        return jsonify({'error': 'invalid_dimension'}), 400
    if metric not in ('activation', 'deal_post', 'wau'):
        return jsonify({'error': 'invalid_metric'}), 400
    
    results = []
    
    if dimension == 'specialty':
        if metric == 'activation':
            rows = db.session.execute(text("""
                SELECT 
                    u.specialty AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN first_action.first_at IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN (
                    SELECT author_id, MIN(created_at) AS first_at
                    FROM posts
                    GROUP BY author_id
                    UNION ALL
                    SELECT author_id, MIN(created_at) AS first_at
                    FROM comments
                    GROUP BY author_id
                ) first_action ON first_action.author_id = u.id
                    AND first_action.first_at <= u.verified_at + INTERVAL '7 days'
                WHERE u.verification_status = 'verified'
                GROUP BY u.specialty
                ORDER BY users DESC
            """))
        elif metric == 'deal_post':
            rows = db.session.execute(text("""
                SELECT 
                    u.specialty AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN p.id IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN posts p ON p.author_id = u.id AND p.post_type = 'deal'
                WHERE u.verification_status = 'verified'
                GROUP BY u.specialty
                ORDER BY users DESC
            """))
        else:  # wau
            rows = db.session.execute(text("""
                SELECT 
                    u.specialty AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN ua.user_id IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN user_activity ua ON ua.user_id = u.id AND ua.created_at >= :start
                WHERE u.verification_status = 'verified'
                GROUP BY u.specialty
                ORDER BY users DESC
            """), {"start": window_start})
        
        for row in rows:
            users_count = int(row.users or 0)
            activated_count = int(row.activated or 0)
            pct = round((activated_count / users_count * 100) if users_count else 0, 1)
            results.append({
                'key': row.key or 'Unknown',
                'users': users_count,
                'activated_pct': pct
            })
    
    elif dimension == 'invite_source':
        if metric == 'activation':
            rows = db.session.execute(text("""
                SELECT 
                    CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN first_action.first_at IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN (
                    SELECT author_id, MIN(created_at) AS first_at
                    FROM posts
                    GROUP BY author_id
                    UNION ALL
                    SELECT author_id, MIN(created_at) AS first_at
                    FROM comments
                    GROUP BY author_id
                ) first_action ON first_action.author_id = u.id
                    AND first_action.first_at <= u.verified_at + INTERVAL '7 days'
                WHERE u.verification_status = 'verified'
                GROUP BY CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END
            """))
        elif metric == 'deal_post':
            rows = db.session.execute(text("""
                SELECT 
                    CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN p.id IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN posts p ON p.author_id = u.id AND p.post_type = 'deal'
                WHERE u.verification_status = 'verified'
                GROUP BY CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END
            """))
        else:  # wau
            rows = db.session.execute(text("""
                SELECT 
                    CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END AS key,
                    COUNT(DISTINCT u.id) AS users,
                    COUNT(DISTINCT CASE WHEN ua.user_id IS NOT NULL THEN u.id END) AS activated
                FROM users u
                LEFT JOIN user_activity ua ON ua.user_id = u.id AND ua.created_at >= :start
                WHERE u.verification_status = 'verified'
                GROUP BY CASE WHEN u.invite_id IS NULL THEN 'admin' ELSE 'peer' END
            """), {"start": window_start})
        
        for row in rows:
            users_count = int(row.users or 0)
            activated_count = int(row.activated or 0)
            pct = round((activated_count / users_count * 100) if users_count else 0, 1)
            results.append({
                'key': row.key,
                'users': users_count,
                'activated_pct': pct
            })
    
    elif dimension == 'verification_week':
        rows = db.session.execute(text("""
            SELECT 
                DATE_TRUNC('week', u.verified_at) AS week_start,
                COUNT(DISTINCT u.id) AS users,
                COUNT(DISTINCT CASE WHEN first_action.first_at IS NOT NULL THEN u.id END) AS activated
            FROM users u
            LEFT JOIN (
                SELECT author_id, MIN(created_at) AS first_at
                FROM posts
                GROUP BY author_id
                UNION ALL
                SELECT author_id, MIN(created_at) AS first_at
                FROM comments
                GROUP BY author_id
            ) first_action ON first_action.author_id = u.id
                AND first_action.first_at <= u.verified_at + INTERVAL '7 days'
            WHERE u.verified_at IS NOT NULL
            GROUP BY DATE_TRUNC('week', u.verified_at)
            ORDER BY week_start DESC
            LIMIT 12
        """))
        
        for row in rows:
            users_count = int(row.users or 0)
            activated_count = int(row.activated or 0)
            pct = round((activated_count / users_count * 100) if users_count else 0, 1)
            week_key = row.week_start.strftime('%Y-%m-%d') if row.week_start else 'Unknown'
            results.append({
                'key': week_key,
                'users': users_count,
                'activated_pct': pct
            })
    
    return jsonify({
        'dimension': dimension,
        'metric': metric,
        'results': results
    }), 200


# ============================================================================
# EXPERT AMAs
# ============================================================================

@app.route('/amas')
@login_required
def amas():
    """List all upcoming and past AMAs."""
    now = datetime.utcnow()
    upcoming = ExpertAMA.query.filter(
        ExpertAMA.status.in_(['scheduled', 'live']),
        ExpertAMA.scheduled_for >= now
    ).order_by(ExpertAMA.scheduled_for.asc()).all()
    
    past = ExpertAMA.query.filter(
        ExpertAMA.status == 'ended'
    ).order_by(ExpertAMA.scheduled_for.desc()).limit(10).all()
    
    return render_template('amas.html', upcoming=upcoming, past=past)


@app.route('/amas/<int:ama_id>')
@login_required
def ama_detail(ama_id):
    """View AMA details and questions."""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    # Check registration
    is_registered = AMARegistration.query.filter_by(
        ama_id=ama_id, user_id=current_user.id
    ).first() is not None
    
    # Get questions sorted by upvotes
    questions = AMAQuestion.query.filter_by(ama_id=ama_id).order_by(
        AMAQuestion.upvotes.desc(), AMAQuestion.asked_at.desc()
    ).all()
    
    return render_template('ama_detail.html', ama=ama, questions=questions, is_registered=is_registered)


@app.route('/amas/<int:ama_id>/register', methods=['POST'])
@login_required
def ama_register(ama_id):
    """Register for an AMA."""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    existing = AMARegistration.query.filter_by(ama_id=ama_id, user_id=current_user.id).first()
    if existing:
        flash('You are already registered for this AMA.', 'info')
        return redirect(url_for('ama_detail', ama_id=ama_id))
    
    if ama.max_participants and ama.participant_count >= ama.max_participants:
        flash('This AMA is full.', 'warning')
        return redirect(url_for('ama_detail', ama_id=ama_id))
    
    reg = AMARegistration(ama_id=ama_id, user_id=current_user.id)
    db.session.add(reg)
    ama.participant_count = (ama.participant_count or 0) + 1
    db.session.commit()
    
    flash('Successfully registered for the AMA!', 'success')
    return redirect(url_for('ama_detail', ama_id=ama_id))


@app.route('/amas/<int:ama_id>/question', methods=['POST'])
@login_required
def ama_ask_question(ama_id):
    """Ask a question in an AMA."""
    ama = ExpertAMA.query.get_or_404(ama_id)
    
    question_text = request.form.get('question', '').strip()
    is_anonymous = request.form.get('is_anonymous') == 'on'
    
    if not question_text:
        flash('Please enter a question.', 'warning')
        return redirect(url_for('ama_detail', ama_id=ama_id))
    
    q = AMAQuestion(
        ama_id=ama_id,
        user_id=current_user.id,
        question=question_text,
        is_anonymous=is_anonymous
    )
    db.session.add(q)
    ama.question_count = (ama.question_count or 0) + 1
    db.session.commit()
    
    flash('Your question has been submitted!', 'success')
    return redirect(url_for('ama_detail', ama_id=ama_id))


@app.route('/amas/<int:ama_id>/question/<int:question_id>/upvote', methods=['POST'])
@login_required
def ama_upvote_question(ama_id, question_id):
    """Upvote an AMA question."""
    q = AMAQuestion.query.get_or_404(question_id)
    q.upvotes = (q.upvotes or 0) + 1
    db.session.commit()
    return jsonify({'upvotes': q.upvotes})


# ============================================================================
# INVESTMENT DEAL MARKETPLACE
# ============================================================================

@app.route('/deals')
@login_required
def deals():
    """Browse investment deals."""
    deal_type = request.args.get('type')
    
    query = InvestmentDeal.query.filter_by(status='active')
    if deal_type:
        query = query.filter_by(deal_type=deal_type)
    
    featured = query.filter_by(is_featured=True).order_by(InvestmentDeal.created_at.desc()).limit(3).all()
    all_deals = query.order_by(InvestmentDeal.created_at.desc()).all()
    
    deal_types = ['real_estate', 'fund', 'practice', 'syndicate']
    
    return render_template('deals.html', featured=featured, deals=all_deals, deal_types=deal_types, current_type=deal_type)


@app.route('/deals/<int:deal_id>')
@login_required
def deal_detail(deal_id):
    """View investment deal details."""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    # Increment view count
    deal.view_count = (deal.view_count or 0) + 1
    db.session.commit()
    
    # Check if user has expressed interest
    user_interest = DealInterest.query.filter_by(deal_id=deal_id, user_id=current_user.id).first()
    
    return render_template('deal_detail.html', deal=deal, user_interest=user_interest)


@app.route('/deals/<int:deal_id>/interest', methods=['POST'])
@login_required
def deal_express_interest(deal_id):
    """Express interest in a deal."""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    existing = DealInterest.query.filter_by(deal_id=deal_id, user_id=current_user.id).first()
    if existing:
        flash('You have already expressed interest in this deal.', 'info')
        return redirect(url_for('deal_detail', deal_id=deal_id))
    
    investment_amount = request.form.get('investment_amount', type=float)
    message = request.form.get('message', '').strip()
    
    interest = DealInterest(
        deal_id=deal_id,
        user_id=current_user.id,
        investment_amount=investment_amount,
        message=message
    )
    db.session.add(interest)
    deal.interest_count = (deal.interest_count or 0) + 1
    db.session.commit()
    
    flash('Your interest has been recorded. The sponsor will contact you.', 'success')
    return redirect(url_for('deal_detail', deal_id=deal_id))


# ============================================================================
# MENTORSHIP
# ============================================================================

@app.route('/mentorship')
@login_required
def mentorship():
    """Mentorship program landing page."""
    # Get available mentors (users with high reputation who opted in)
    mentors = User.query.filter(
        User.verification_status == 'verified',
        User.reputation_score >= 100
    ).order_by(User.reputation_score.desc()).limit(20).all()
    
    # User's mentorships
    my_mentorships = Mentorship.query.filter(
        (Mentorship.mentor_id == current_user.id) | (Mentorship.mentee_id == current_user.id)
    ).order_by(Mentorship.created_at.desc()).all()
    
    return render_template('mentorship.html', mentors=mentors, my_mentorships=my_mentorships)


@app.route('/mentorship/request/<int:mentor_id>', methods=['POST'])
@login_required
def request_mentorship(mentor_id):
    """Request mentorship from a user."""
    mentor = User.query.get_or_404(mentor_id)
    
    if mentor.id == current_user.id:
        flash('You cannot mentor yourself.', 'warning')
        return redirect(url_for('mentorship'))
    
    existing = Mentorship.query.filter_by(
        mentor_id=mentor_id, mentee_id=current_user.id
    ).filter(Mentorship.status.in_(['pending', 'active'])).first()
    
    if existing:
        flash('You already have a mentorship request with this user.', 'info')
        return redirect(url_for('mentorship'))
    
    focus_areas = request.form.get('focus_areas', '')
    
    m = Mentorship(
        mentor_id=mentor_id,
        mentee_id=current_user.id,
        focus_areas=focus_areas,
        status='pending'
    )
    db.session.add(m)
    db.session.commit()
    
    flash('Mentorship request sent!', 'success')
    return redirect(url_for('mentorship'))


@app.route('/mentorship/<int:mentorship_id>/accept', methods=['POST'])
@login_required
def accept_mentorship(mentorship_id):
    """Accept a mentorship request."""
    m = Mentorship.query.get_or_404(mentorship_id)
    
    if m.mentor_id != current_user.id:
        flash('You cannot accept this request.', 'danger')
        return redirect(url_for('mentorship'))
    
    m.status = 'active'
    m.start_date = datetime.utcnow()
    m.end_date = datetime.utcnow() + timedelta(days=90)  # 3 months
    db.session.commit()
    
    flash('Mentorship accepted!', 'success')
    return redirect(url_for('mentorship'))


# ============================================================================
# COURSES
# ============================================================================

@app.route('/courses')
@login_required
def courses():
    """Browse available courses."""
    featured = Course.query.filter_by(is_published=True, is_featured=True).all()
    all_courses = Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).all()
    
    # User's enrollments
    enrolled_ids = [e.course_id for e in CourseEnrollment.query.filter_by(user_id=current_user.id).all()]
    
    return render_template('courses.html', featured=featured, courses=all_courses, enrolled_ids=enrolled_ids)


@app.route('/courses/<int:course_id>')
@login_required
def course_detail(course_id):
    """View course details."""
    course = Course.query.get_or_404(course_id)
    modules = CourseModule.query.filter_by(course_id=course_id).order_by(CourseModule.order_index).all()
    
    enrollment = CourseEnrollment.query.filter_by(course_id=course_id, user_id=current_user.id).first()
    
    return render_template('course_detail.html', course=course, modules=modules, enrollment=enrollment)


# ============================================================================
# EVENTS
# ============================================================================

@app.route('/events')
@login_required
def events():
    """Browse upcoming events."""
    now = datetime.utcnow()
    
    upcoming = Event.query.filter(
        Event.is_published == True,
        Event.start_date >= now
    ).order_by(Event.start_date.asc()).all()
    
    past = Event.query.filter(
        Event.is_published == True,
        Event.end_date < now
    ).order_by(Event.end_date.desc()).limit(5).all()
    
    return render_template('events.html', upcoming=upcoming, past=past)


@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    """View event details."""
    event = Event.query.get_or_404(event_id)
    sessions = EventSession.query.filter_by(event_id=event_id).order_by(EventSession.start_time).all()
    
    registration = EventRegistration.query.filter_by(event_id=event_id, user_id=current_user.id).first()
    
    return render_template('event_detail.html', event=event, sessions=sessions, registration=registration)


# ============================================================================
# REFERRAL PROGRAM
# ============================================================================

@app.route('/referral')
@login_required
def referral():
    """Referral program page."""
    # Generate referral code if not exists
    if not current_user.referral_code:
        import random, string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        current_user.referral_code = code
        db.session.commit()
    
    # Get referral stats
    referrals = Referral.query.filter_by(referrer_id=current_user.id).all()
    completed_count = len([r for r in referrals if r.status == 'completed'])
    
    return render_template('referral.html', 
        referral_code=current_user.referral_code,
        referrals=referrals,
        completed_count=completed_count
    )


# ============================================================================
# PREMIUM SUBSCRIPTION
# ============================================================================

@app.route('/premium')
@login_required
def premium():
    """Premium subscription page."""
    current_sub = Subscription.query.filter_by(
        user_id=current_user.id, status='active'
    ).first()
    
    return render_template('premium.html', current_subscription=current_sub)


# ============================================================================
# ANALYTICS API
# ============================================================================

@app.route('/api/admin/analytics/overview')
@login_required
def admin_analytics_overview():
    """Get analytics overview data."""
    decision = can(current_user, Actions.VIEW_ANALYTICS)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    
    # Verified WAU
    verified_wau = db.session.query(UserActivity.user_id).distinct().join(
        User, UserActivity.user_id == User.id
    ).filter(
        User.is_verified == True,
        UserActivity.created_at >= week_ago
    ).count()
    
    # Deal WAU (users who interacted with deals)
    deal_wau = db.session.query(UserActivity.user_id).distinct().filter(
        UserActivity.entity_type == 'deal',
        UserActivity.created_at >= week_ago
    ).count()
    
    # TTFV (Time to First Verification) - median days
    verified_users = User.query.filter(User.verified_at.isnot(None)).all()
    ttfv_days = []
    for u in verified_users:
        if u.verification_submitted_at and u.verified_at:
            delta = (u.verified_at - u.verification_submitted_at).days
            ttfv_days.append(delta)
    ttfv_p50 = sorted(ttfv_days)[len(ttfv_days)//2] if ttfv_days else 0
    
    # Verification SLA
    pending = VerificationQueueEntry.query.filter_by(status='pending').all()
    wait_hours = [(now - p.submitted_at).total_seconds() / 3600 for p in pending]
    wait_hours.sort()
    sla_p50 = wait_hours[len(wait_hours)//2] if wait_hours else 0
    sla_p95 = wait_hours[int(len(wait_hours) * 0.95)] if wait_hours else 0
    
    # Invites in last 7 days
    invites_issued = Invite.query.filter(Invite.created_at >= week_ago).count()
    invites_accepted = Invite.query.filter(
        Invite.accepted_at >= week_ago,
        Invite.accepted_at.isnot(None)
    ).count()
    
    return jsonify({
        'verified_wau': verified_wau,
        'deal_wau': deal_wau,
        'ttfv_p50_days': ttfv_p50,
        'verification_sla_p50_hours': round(sla_p50, 1),
        'verification_sla_p95_hours': round(sla_p95, 1),
        'invites_7d_issued': invites_issued,
        'invites_7d_accepted': invites_accepted
    })


@app.route('/api/admin/analytics/cohorts')
@login_required
def admin_analytics_cohorts():
    """Get cohort analytics data."""
    decision = can(current_user, Actions.VIEW_ANALYTICS)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    # Activation by specialty (verified in last 30 days)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    specialty_stats = db.session.query(
        User.specialty,
        db.func.count(User.id).label('total'),
        db.func.sum(db.case((User.is_verified == True, 1), else_=0)).label('verified')
    ).filter(
        User.created_at >= month_ago
    ).group_by(User.specialty).all()
    
    cohorts = []
    for stat in specialty_stats:
        cohorts.append({
            'specialty': stat.specialty or 'Unknown',
            'total': stat.total,
            'verified': stat.verified or 0,
            'activation_rate': round((stat.verified or 0) / stat.total * 100, 1) if stat.total > 0 else 0
        })
    
    return jsonify({'cohorts': cohorts})


# ============================================================================
# REPORTING API
# ============================================================================

@app.route('/api/reports', methods=['POST'])
@login_required
def submit_report():
    """Submit a content report."""
    decision = can(current_user, Actions.SUBMIT_REPORT)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json()
    entity_type = data.get('entity_type')
    entity_id = data.get('entity_id')
    reason = data.get('reason')
    details = data.get('details')
    
    if not all([entity_type, entity_id, reason]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check for duplicate report
    existing = ContentReport.query.filter_by(
        reporter_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id
    ).first()
    
    if existing:
        return jsonify({'error': 'You have already reported this content'}), 409
    
    report = ContentReport(
        reporter_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        details=details
    )
    db.session.add(report)
    db.session.commit()
    
    # Trigger auto-moderation
    from moderation_engine import process_new_report
    process_new_report(report)
    
    # Log activity
    from activity import log_report_submit
    log_report_submit(current_user.id, report.id)
    
    return jsonify({'success': True, 'report_id': report.id}), 201


@app.route('/api/admin/reports')
@login_required
def admin_reports():
    """List content reports."""
    decision = can(current_user, Actions.VIEW_REPORTS)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    status = request.args.get('status', 'open')
    reports = ContentReport.query.filter_by(status=status).order_by(ContentReport.created_at.desc()).all()
    
    return jsonify({'reports': [{
        'id': r.id,
        'entity_type': r.entity_type,
        'entity_id': r.entity_id,
        'reason': r.reason,
        'details': r.details,
        'reporter_id': r.reporter_id,
        'created_at': r.created_at.isoformat()
    } for r in reports]})


@app.route('/api/admin/reports/<int:report_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_report(report_id):
    """Resolve a content report."""
    decision = can(current_user, Actions.RESOLVE_REPORT)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json()
    resolution = data.get('resolution', 'no_action')
    
    from moderation_engine import resolve_report
    success, msg = resolve_report(report_id, current_user.id, resolution)
    
    if not success:
        return jsonify({'error': msg}), 400
    
    return jsonify({'success': True})


# ============================================================================
# DEAL OUTCOMES API
# ============================================================================

@app.route('/api/deals/<int:deal_id>/outcome', methods=['GET', 'POST'])
@login_required
def deal_outcome(deal_id):
    """Get or submit deal outcome."""
    deal = InvestmentDeal.query.get_or_404(deal_id)
    
    if request.method == 'GET':
        outcome = DealOutcome.query.filter_by(deal_id=deal_id).first()
        if not outcome:
            return jsonify({'outcome': None})
        
        return jsonify({'outcome': {
            'id': outcome.id,
            'outcome_status': outcome.outcome_status,
            'actual_return': outcome.actual_return,
            'actual_term': outcome.actual_term,
            'lessons_learned': outcome.lessons_learned if outcome.is_public else None,
            'would_invest_again': outcome.would_invest_again
        }})
    
    # POST - submit outcome
    decision = can(current_user, Actions.SUBMIT_DEAL_OUTCOME)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    # Only deal creator or admin can submit
    if deal.created_by_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    
    existing = DealOutcome.query.filter_by(deal_id=deal_id).first()
    if existing:
        existing.outcome_status = data.get('outcome_status', existing.outcome_status)
        existing.actual_return = data.get('actual_return')
        existing.actual_term = data.get('actual_term')
        existing.lessons_learned = data.get('lessons_learned')
        existing.would_invest_again = data.get('would_invest_again')
        existing.updated_at = datetime.utcnow()
    else:
        existing = DealOutcome(
            deal_id=deal_id,
            submitted_by_id=current_user.id,
            outcome_status=data.get('outcome_status'),
            actual_return=data.get('actual_return'),
            actual_term=data.get('actual_term'),
            lessons_learned=data.get('lessons_learned'),
            would_invest_again=data.get('would_invest_again')
        )
        db.session.add(existing)
    
    # Update deal status
    if data.get('outcome_status') in ('closed_success', 'closed_loss', 'passed'):
        deal.status = 'closed'
    
    db.session.commit()
    
    # Log activity
    from activity import log_outcome_submit
    log_outcome_submit(current_user.id, deal_id)
    
    return jsonify({'success': True})


# ============================================================================
# SPONSOR PROFILES API
# ============================================================================

@app.route('/api/sponsors/profile', methods=['GET', 'POST'])
@login_required
def sponsor_profile_self():
    """Get or submit own sponsor profile."""
    if request.method == 'GET':
        profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
        if not profile:
            return jsonify({'profile': None})
        
        return jsonify({'profile': {
            'company_name': profile.company_name,
            'company_description': profile.company_description,
            'company_website': profile.company_website,
            'years_in_business': profile.years_in_business,
            'aum': profile.aum,
            'track_record': profile.track_record,
            'status': profile.status
        }})
    
    # POST - submit profile
    decision = can(current_user, Actions.SUBMIT_SPONSOR_PROFILE)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json()
    
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.company_name = data.get('company_name', profile.company_name)
        profile.company_description = data.get('company_description')
        profile.company_website = data.get('company_website')
        profile.years_in_business = data.get('years_in_business')
        profile.aum = data.get('aum')
        profile.track_record = data.get('track_record')
        profile.status = 'pending'
        profile.updated_at = datetime.utcnow()
    else:
        profile = SponsorProfile(
            user_id=current_user.id,
            company_name=data.get('company_name'),
            company_description=data.get('company_description'),
            company_website=data.get('company_website'),
            years_in_business=data.get('years_in_business'),
            aum=data.get('aum'),
            track_record=data.get('track_record')
        )
        db.session.add(profile)
    
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/sponsors/<int:user_id>/profile')
@login_required
def sponsor_profile(user_id):
    """Get sponsor profile (approved only unless admin/self)."""
    profile = SponsorProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    # Only show if approved, or if requesting own profile, or if admin
    if profile.status != 'approved' and user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Profile not approved'}), 403
    
    return jsonify({'profile': {
        'user_id': profile.user_id,
        'company_name': profile.company_name,
        'company_description': profile.company_description,
        'company_website': profile.company_website,
        'years_in_business': profile.years_in_business,
        'total_deals': profile.total_deals,
        'aum': profile.aum,
        'track_record': profile.track_record,
        'status': profile.status
    }})


@app.route('/api/sponsors/<int:user_id>/reviews', methods=['GET', 'POST'])
@login_required
def sponsor_reviews(user_id):
    """Get or submit sponsor reviews."""
    if request.method == 'GET':
        reviews = SponsorReview.query.filter_by(sponsor_id=user_id, is_public=True).order_by(SponsorReview.created_at.desc()).all()
        return jsonify({'reviews': [{
            'id': r.id,
            'rating': r.rating,
            'review_text': r.review_text,
            'is_verified_investment': r.is_verified_investment,
            'created_at': r.created_at.isoformat()
        } for r in reviews]})
    
    # POST - submit review
    decision = can(current_user, Actions.SUBMIT_SPONSOR_REVIEW)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json()
    
    review = SponsorReview(
        sponsor_id=user_id,
        reviewer_id=current_user.id,
        deal_id=data.get('deal_id'),
        rating=data.get('rating'),
        review_text=data.get('review_text')
    )
    db.session.add(review)
    db.session.commit()
    
    return jsonify({'success': True}), 201


@app.route('/api/admin/sponsors/<int:user_id>/status', methods=['POST'])
@login_required
def admin_sponsor_status(user_id):
    """Approve or reject sponsor profile."""
    decision = can(current_user, Actions.APPROVE_SPONSOR)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    profile = SponsorProfile.query.filter_by(user_id=user_id).first_or_404()
    data = request.get_json()
    
    action = data.get('action')
    if action == 'approve':
        profile.status = 'approved'
        profile.approved_at = datetime.utcnow()
        profile.approved_by_id = current_user.id
    elif action == 'reject':
        profile.status = 'rejected'
        profile.rejection_reason = data.get('reason')
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# ONBOARDING PROMPTS API
# ============================================================================

@app.route('/api/onboarding/prompt')
@login_required
def get_onboarding_prompt():
    """Get next onboarding prompt for user."""
    decision = can(current_user, Actions.VIEW_ONBOARDING)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    # Get dismissed prompts
    dismissed_ids = [d.prompt_id for d in UserPromptDismissal.query.filter_by(user_id=current_user.id).all()]
    
    # Find cohort-appropriate prompt
    cohorts = ['all', f"specialty_{current_user.specialty}"]
    if current_user.created_at and (datetime.utcnow() - current_user.created_at).days < 7:
        cohorts.append('new_user')
    
    prompt = OnboardingPrompt.query.filter(
        OnboardingPrompt.is_active == True,
        OnboardingPrompt.target_cohort.in_(cohorts),
        ~OnboardingPrompt.id.in_(dismissed_ids)
    ).order_by(OnboardingPrompt.priority.desc()).first()
    
    if not prompt:
        return jsonify({'prompt': None})
    
    return jsonify({'prompt': {
        'id': prompt.id,
        'title': prompt.title,
        'message': prompt.message,
        'action_url': prompt.action_url,
        'action_label': prompt.action_label
    }})


@app.route('/api/onboarding/prompt/dismiss', methods=['POST'])
@login_required
def dismiss_onboarding_prompt():
    """Dismiss an onboarding prompt."""
    decision = can(current_user, Actions.DISMISS_PROMPT)
    if not decision.allowed:
        return deny_response(decision.reason)
    
    data = request.get_json()
    prompt_id = data.get('prompt_id')
    
    if not prompt_id:
        return jsonify({'error': 'prompt_id required'}), 400
    
    existing = UserPromptDismissal.query.filter_by(
        user_id=current_user.id, prompt_id=prompt_id
    ).first()
    
    if not existing:
        dismissal = UserPromptDismissal(user_id=current_user.id, prompt_id=prompt_id)
        db.session.add(dismissal)
        db.session.commit()
    
    return jsonify({'success': True})


# ============================================================================
# INVESTMENT ROOMS
# ============================================================================

@app.route('/rooms')
@login_required
def rooms():
    """Browse specialty investment rooms."""
    all_rooms = InvestmentRoom.query.filter_by(is_active=True).order_by(InvestmentRoom.member_count.desc()).all()
    
    # Get user's joined room IDs
    user_memberships = RoomMembership.query.filter_by(user_id=current_user.id).all()
    user_room_ids = [m.room_id for m in user_memberships]
    
    # Get user's joined rooms
    user_rooms = [room for room in all_rooms if room.id in user_room_ids]
    
    # Group rooms by category
    specialty_rooms = [r for r in all_rooms if r.category == 'specialty']
    career_stage_rooms = [r for r in all_rooms if r.category == 'career_stage']
    topic_rooms = [r for r in all_rooms if r.category == 'topic']
    
    return render_template('rooms.html', 
                          rooms=all_rooms, 
                          user_rooms=user_rooms,
                          specialty_rooms=specialty_rooms,
                          career_stage_rooms=career_stage_rooms,
                          topic_rooms=topic_rooms,
                          user_room_ids=user_room_ids)


@app.route('/rooms/<int:room_id>')
@login_required
def room_detail(room_id):
    """View a specific investment room."""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    # Check if user is a member
    membership = RoomMembership.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    
    # Get room posts
    posts = Post.query.filter_by(room_id=room_id, is_published=True).order_by(Post.created_at.desc()).limit(50).all()
    
    # Stats object for template
    stats = {
        'is_member': membership is not None,
        'members': room.member_count or 0,
        'posts': room.post_count or 0
    }
    
    return render_template('room_detail.html',
                          room=room,
                          stats=stats,
                          posts=posts)


@app.route('/room/<int:room_id>/post', methods=['POST'])
@login_required
def create_room_post(room_id):
    """Create a post in a specific room."""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    # Check membership
    membership = RoomMembership.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    if not membership:
        flash('You must join this room to post.', 'warning')
        return redirect(url_for('room_detail', room_id=room_id))
    
    content = request.form.get('content', '').strip()
    post_type = request.form.get('post_type', 'general')
    tags = request.form.get('tags', '')
    is_anonymous = request.form.get('anonymous') == 'true'
    
    if not content:
        flash('Post content cannot be empty.', 'error')
        return redirect(url_for('room_detail', room_id=room_id))
    
    post = Post()
    post.author_id = current_user.id
    post.room_id = room_id
    post.content = content
    post.post_type = post_type
    post.tags = tags
    post.is_anonymous = is_anonymous
    
    try:
        db.session.add(post)
        room.post_count = (room.post_count or 0) + 1
        db.session.commit()
        flash('Post created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating room post: {e}")
        flash('Error creating post. Please try again.', 'error')
    
    return redirect(url_for('room_detail', room_id=room_id))


@app.route('/rooms/<int:room_id>/join', methods=['POST'])
@login_required
def join_room(room_id):
    """Join an investment room."""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    existing = RoomMembership.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    if existing:
        flash('You are already a member of this room.', 'info')
        return redirect(url_for('room_detail', room_id=room_id))
    
    membership = RoomMembership(user_id=current_user.id, room_id=room_id)
    db.session.add(membership)
    room.member_count = (room.member_count or 0) + 1
    db.session.commit()
    
    flash(f'Welcome to {room.name}!', 'success')
    return redirect(url_for('room_detail', room_id=room_id))


@app.route('/rooms/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_room(room_id):
    """Leave an investment room."""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    membership = RoomMembership.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    if not membership:
        flash('You are not a member of this room.', 'info')
        return redirect(url_for('rooms'))
    
    db.session.delete(membership)
    room.member_count = max((room.member_count or 1) - 1, 0)
    db.session.commit()
    
    flash(f'You have left {room.name}.', 'info')
    return redirect(url_for('rooms'))


# ============================================================================
# TRENDING TOPICS
# ============================================================================

@app.route('/trending')
@login_required
def trending():
    """View trending topics and hashtags."""
    # Get top trending hashtags by weekly count
    trending_hashtags = Hashtag.query.order_by(Hashtag.weekly_count.desc()).limit(20).all()
    
    # Create trending data structure for template
    trending_data = []
    trending_posts = {}
    
    for hashtag in trending_hashtags:
        trending_data.append({
            'tag': hashtag.name,
            'post_count': hashtag.post_count or 0,
            'mention_count': hashtag.weekly_count or 0,
            'last_mentioned': hashtag.last_used or datetime.utcnow()
        })
        
        # Get top posts for this hashtag
        post_ids = [ph.post_id for ph in PostHashtag.query.filter_by(hashtag_id=hashtag.id).limit(3).all()]
        if post_ids:
            posts = Post.query.filter(Post.id.in_(post_ids), Post.is_published == True).order_by(Post.created_at.desc()).all()
            trending_posts[hashtag.name] = posts
    
    return render_template('trending.html',
                          trending=trending_data,
                          trending_posts=trending_posts)


@app.route('/tag/<tag_name>')
@login_required
def view_tag(tag_name):
    """View all posts with a specific hashtag."""
    hashtag = Hashtag.query.filter_by(name=tag_name.lower()).first()
    
    posts = []
    if hashtag:
        post_ids = [ph.post_id for ph in PostHashtag.query.filter_by(hashtag_id=hashtag.id).all()]
        posts = Post.query.filter(Post.id.in_(post_ids), Post.is_published == True).order_by(Post.created_at.desc()).limit(50).all()
    
    return render_template('tag_posts.html',
                          tag=tag_name,
                          hashtag=hashtag,
                          posts=posts)


# ============================================================================
# ACHIEVEMENTS & GAMIFICATION
# ============================================================================

@app.route('/achievements')
@login_required
def achievements_page():
    """View achievements and leaderboard."""
    # Get all achievements
    all_achievements = Achievement.query.filter_by(is_active=True).order_by(Achievement.category, Achievement.tier).all()
    
    # Get user's earned achievements
    user_achievement_ids = [ua.achievement_id for ua in UserAchievement.query.filter_by(user_id=current_user.id).all()]
    
    # Get user's points record
    points_record = UserPoints.query.filter_by(user_id=current_user.id).first()
    if not points_record:
        points_record = UserPoints(user_id=current_user.id)
        db.session.add(points_record)
        db.session.commit()
    
    # Get leaderboard (top 10 by points) - return User objects with their points
    leaderboard_data = db.session.query(User, UserPoints).join(UserPoints).order_by(UserPoints.total_points.desc()).limit(10).all()
    
    # Create leaderboard as list of users with points attribute
    leaderboard = []
    for user, points in leaderboard_data:
        user.total_points = points.total_points
        user.achievement_count = len(UserAchievement.query.filter_by(user_id=user.id).all())
        leaderboard.append(user)
    
    # Calculate progress percentage
    earned_count = len(user_achievement_ids)
    total_count = len(all_achievements)
    progress_percent = int((earned_count / total_count * 100) if total_count > 0 else 0)
    
    # Group achievements by category
    achievements_by_category = {}
    for achievement in all_achievements:
        cat = achievement.category or 'general'
        if cat not in achievements_by_category:
            achievements_by_category[cat] = []
        achievements_by_category[cat].append({
            'achievement': achievement,
            'earned': achievement.id in user_achievement_ids
        })
    
    return render_template('achievements.html',
                          achievements_by_category=achievements_by_category,
                          user_points=points_record.total_points or 0,
                          leaderboard=leaderboard,
                          earned_count=earned_count,
                          total_count=total_count,
                          progress_percent=progress_percent)
