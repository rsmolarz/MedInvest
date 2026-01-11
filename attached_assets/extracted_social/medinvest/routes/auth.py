"""
Authentication Routes - Login, Register, Logout
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app import db
from models import User, Referral

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            
            # Update last login and streak
            if user.last_login:
                days_since = (datetime.utcnow() - user.last_login).days
                if days_since == 1:
                    user.login_streak += 1
                elif days_since > 1:
                    user.login_streak = 1
            else:
                user.login_streak = 1
            
            user.last_login = datetime.utcnow()
            user.add_points(1)  # Daily login point
            db.session.commit()
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.feed'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        specialty = request.form.get('specialty', '')
        referral_code = request.form.get('referral_code', '').strip().upper()
        
        # Validation
        if not all([email, password, first_name, last_name]):
            flash('All fields are required', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('auth/register.html')
        
        # Create user
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            specialty=specialty if specialty else None
        )
        user.set_password(password)
        user.generate_referral_code()
        
        # Handle referral
        referred_by = None
        if referral_code:
            referred_by = User.query.filter_by(referral_code=referral_code).first()
            if referred_by:
                user.referred_by_id = referred_by.id
                user.add_points(50)  # Bonus for being referred
        
        db.session.add(user)
        db.session.commit()
        
        # Create referral record and reward referrer
        if referred_by:
            referral = Referral(
                referrer_id=referred_by.id,
                referred_user_id=user.id,
                referred_user_activated=True
            )
            referred_by.add_points(100)  # Reward for referring
            db.session.add(referral)
            db.session.commit()
        
        login_user(user)
        flash('Welcome to MedInvest! Your account has been created.', 'success')
        return redirect(url_for('main.feed'))
    
    # Pre-fill referral code from URL
    ref_code = request.args.get('ref', '')
    return render_template('auth/register.html', referral_code=ref_code)


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))
