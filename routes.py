from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from models import User, Module, UserProgress, ForumTopic, ForumPost, PortfolioTransaction, Resource
from datetime import datetime
import logging
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

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

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
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            medical_license=medical_license,
            specialty=specialty,
            hospital_affiliation=hospital_affiliation
        )
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
    # Get user's progress
    completed_modules = UserProgress.query.filter_by(user_id=current_user.id, completed=True).count()
    total_modules = Module.query.filter_by(is_published=True).count()
    
    # Get recent modules
    recent_modules = Module.query.filter_by(is_published=True).order_by(Module.created_at.desc()).limit(3).all()
    
    # Get recent forum activity
    recent_posts = ForumPost.query.join(ForumTopic).order_by(ForumPost.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         completed_modules=completed_modules,
                         total_modules=total_modules,
                         recent_modules=recent_modules,
                         recent_posts=recent_posts)

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
        progress = UserProgress(user_id=current_user.id, module_id=module_id)
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
    
    query = ForumTopic.query.filter_by(is_active=True)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    topics = query.order_by(ForumTopic.created_at.desc()).all()
    
    categories = db.session.query(ForumTopic.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template('forums.html', topics=topics, categories=categories, selected_category=category)

@app.route('/forum/<int:topic_id>')
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
    
    post = ForumPost(
        topic_id=topic_id,
        user_id=current_user.id,
        content=content,
        parent_id=int(parent_id) if parent_id else None
    )
    
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
    
    transaction = PortfolioTransaction(
        user_id=current_user.id,
        symbol=symbol,
        transaction_type=transaction_type,
        quantity=quantity,
        price=price,
        total_amount=total_amount
    )
    
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
    
    return render_template('profile.html', 
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
    
    db.session.commit()
    logging.info("Sample data created successfully")

# Create sample data when the application starts
with app.app_context():
    create_sample_data()
