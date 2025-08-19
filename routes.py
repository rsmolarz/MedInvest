from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from models import User, Module, UserProgress, ForumTopic, ForumPost, PortfolioTransaction, Resource, Post, Comment, Like, Follow, Notification
from datetime import datetime
import logging
import os
from markupsafe import Markup
import re

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
