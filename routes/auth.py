"""
Authentication Routes - Login, Register, Logout
"""
import os
import logging
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from datetime import datetime
from app import db
from models import User, Referral

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Google OAuth Blueprint
# Note: ProxyFix in app.py handles proper Host/Proto headers for custom domains
google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    scope=['openid', 'email', 'profile'],
    redirect_to='auth.google_callback'
)


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
            # Check if 2FA is enabled
            if user.is_2fa_enabled and user.totp_secret:
                # Store user ID in session for 2FA verification
                from flask import session
                session['pending_2fa_user_id'] = user.id
                session['pending_2fa_remember'] = remember
                return redirect(url_for('auth.verify_2fa'))
            
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


@auth_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    """Verify 2FA code during login"""
    from flask import session
    
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if user.verify_totp(code):
            remember = session.pop('pending_2fa_remember', False)
            session.pop('pending_2fa_user_id', None)
            
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
            user.add_points(1)
            db.session.commit()
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('main.feed'))
        else:
            flash('Invalid verification code', 'error')
    
    return render_template('auth/verify_2fa.html')


@auth_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Setup 2FA for the current user"""
    import qrcode
    import io
    import base64
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if current_user.verify_totp(code):
            current_user.is_2fa_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled!', 'success')
            return redirect(url_for('main.security'))
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    # Generate new secret if not exists
    if not current_user.totp_secret:
        current_user.generate_totp_secret()
        db.session.commit()
    
    # Generate QR code
    totp_uri = current_user.get_totp_uri()
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('auth/setup_2fa.html', 
                          qr_code=qr_code_base64,
                          secret=current_user.totp_secret)


@auth_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA for the current user"""
    password = request.form.get('password', '')
    
    if not current_user.check_password(password):
        flash('Incorrect password', 'error')
        return redirect(url_for('main.security'))
    
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    
    flash('Two-factor authentication has been disabled', 'success')
    return redirect(url_for('main.security'))


@auth_bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    if not google.authorized:
        flash('Google login failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Failed to get user info from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        google_info = resp.json()
        email = google_info.get('email')
        google_id = google_info.get('id')
        
        if not email:
            flash('Google account email not available.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.replit_id = f'google_{google_id}'
            if google_info.get('picture') and not user.profile_image_url:
                user.profile_image_url = google_info.get('picture')
        else:
            user = User(
                email=email,
                first_name=google_info.get('given_name', 'User'),
                last_name=google_info.get('family_name', ''),
                replit_id=f'google_{google_id}',
                profile_image_url=google_info.get('picture'),
                specialty='',
                medical_license=f'GOOGLE-{google_id}',
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user)
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        flash('An error occurred during Google login.', 'error')
        return redirect(url_for('auth.login'))
