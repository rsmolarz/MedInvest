from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from models import User, Module, UserProgress, ForumTopic, ForumPost, PortfolioTransaction, Resource, Post, Comment, Like, Follow, Notification, Group, GroupMembership, Connection, DealDetails, DealAnalysis, AiJob
from datetime import datetime
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
    
    if not content:
        flash('Post content cannot be empty.', 'error')
        return redirect(url_for('dashboard'))
    
    post = Post()
    post.author_id = current_user.id
    post.content = content
    post.post_type = post_type
    post.tags = tags
    
    try:
        db.session.add(post)
        db.session.commit()
        flash('Post created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating post: {e}")
        flash('Error creating post. Please try again.', 'error')
    
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
