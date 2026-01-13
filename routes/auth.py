"""
Authentication Routes - Login, Register, Logout, Verification
"""
import os
import logging
import random
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from datetime import datetime, timedelta
from urllib.parse import urlencode
from werkzeug.utils import secure_filename
import secrets
from app import db
from models import User, Referral
from mailer import send_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI', 'https://medmoneyincubator.com/auth/google/callback')

# Facebook OAuth Configuration
FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')
FACEBOOK_REDIRECT_URI = os.environ.get('FACEBOOK_OAUTH_REDIRECT_URI', 'https://medmoneyincubator.com/auth/facebook/callback')

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')
GITHUB_REDIRECT_URI = os.environ.get('GITHUB_OAUTH_REDIRECT_URI', 'https://medmoneyincubator.com/auth/github/callback')

# Google OAuth Blueprint (for compatibility, but we'll use custom routes)
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=['openid', 'email', 'profile'],
    redirect_to='auth.google_callback'
)


@auth_bp.route('/google-login')
def google_login_custom():
    """Custom Google OAuth login that uses explicit redirect_uri"""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'google'
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account'
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    logging.info(f"Redirecting to Google OAuth with redirect_uri: {GOOGLE_REDIRECT_URI}")
    return redirect(auth_url)


@auth_bp.route('/facebook-login')
def facebook_login():
    """Facebook OAuth login with explicit redirect_uri"""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'facebook'
    
    params = {
        'client_id': FACEBOOK_APP_ID,
        'redirect_uri': FACEBOOK_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'email,public_profile',
        'state': state
    }
    
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
    logging.info(f"Redirecting to Facebook OAuth with redirect_uri: {FACEBOOK_REDIRECT_URI}")
    return redirect(auth_url)


@auth_bp.route('/github-login')
def github_login():
    """GitHub OAuth login with explicit redirect_uri"""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'github'
    
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'user:email read:user',
        'state': state
    }
    
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    logging.info(f"Redirecting to GitHub OAuth with redirect_uri: {GITHUB_REDIRECT_URI}")
    return redirect(auth_url)


@auth_bp.route('/github/callback')
def github_callback():
    """Handle GitHub OAuth callback"""
    import requests
    
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    
    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    error = request.args.get('error')
    if error:
        logging.error(f"GitHub OAuth error: {error}")
        flash('GitHub login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))
    
    code = request.args.get('code')
    if not code:
        flash('No authorization code received from GitHub.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        token_url = 'https://github.com/login/oauth/access_token'
        token_data = {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'redirect_uri': GITHUB_REDIRECT_URI,
            'code': code
        }
        headers = {'Accept': 'application/json'}
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        
        if not token_response.ok:
            logging.error(f"GitHub token exchange failed: {token_response.text}")
            flash('Failed to authenticate with GitHub.', 'error')
            return redirect(url_for('auth.login'))
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        
        if not access_token:
            flash('No access token received from GitHub.', 'error')
            return redirect(url_for('auth.login'))
        
        userinfo_url = 'https://api.github.com/user'
        userinfo_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        userinfo_response = requests.get(userinfo_url, headers=userinfo_headers)
        
        if not userinfo_response.ok:
            flash('Failed to get user info from GitHub.', 'error')
            return redirect(url_for('auth.login'))
        
        gh_info = userinfo_response.json()
        gh_id = gh_info.get('id')
        gh_username = gh_info.get('login')
        gh_name = gh_info.get('name') or gh_username
        gh_avatar = gh_info.get('avatar_url')
        
        email = gh_info.get('email')
        if not email:
            emails_url = 'https://api.github.com/user/emails'
            emails_response = requests.get(emails_url, headers=userinfo_headers)
            if emails_response.ok:
                emails = emails_response.json()
                for e in emails:
                    if e.get('primary') and e.get('verified'):
                        email = e.get('email')
                        break
                if not email and emails:
                    email = emails[0].get('email')
        
        if not email:
            flash('GitHub account email not available. Please ensure your GitHub account has a verified email.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email).first()
        
        name_parts = gh_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else 'User'
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        if user:
            user.replit_id = f'github_{gh_id}'
            if gh_avatar and not user.profile_image_url:
                user.profile_image_url = gh_avatar
        else:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                replit_id=f'github_{gh_id}',
                profile_image_url=gh_avatar,
                specialty='',
                medical_license=f'GITHUB-{gh_id}',
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user)
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        logging.error(f"GitHub OAuth error: {str(e)}")
        flash('An error occurred during GitHub login.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/facebook/callback')
def facebook_callback():
    """Handle Facebook OAuth callback"""
    import requests
    
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    
    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    error = request.args.get('error')
    if error:
        logging.error(f"Facebook OAuth error: {error}")
        flash('Facebook login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))
    
    code = request.args.get('code')
    if not code:
        flash('No authorization code received from Facebook.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        token_url = 'https://graph.facebook.com/v18.0/oauth/access_token'
        token_params = {
            'client_id': FACEBOOK_APP_ID,
            'client_secret': FACEBOOK_APP_SECRET,
            'redirect_uri': FACEBOOK_REDIRECT_URI,
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params)
        
        if not token_response.ok:
            logging.error(f"Facebook token exchange failed: {token_response.text}")
            flash('Failed to authenticate with Facebook.', 'error')
            return redirect(url_for('auth.login'))
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        
        if not access_token:
            flash('No access token received from Facebook.', 'error')
            return redirect(url_for('auth.login'))
        
        userinfo_url = 'https://graph.facebook.com/me'
        userinfo_params = {
            'fields': 'id,email,first_name,last_name,picture.type(large)',
            'access_token': access_token
        }
        userinfo_response = requests.get(userinfo_url, params=userinfo_params)
        
        if not userinfo_response.ok:
            flash('Failed to get user info from Facebook.', 'error')
            return redirect(url_for('auth.login'))
        
        fb_info = userinfo_response.json()
        email = fb_info.get('email')
        fb_id = fb_info.get('id')
        
        if not email:
            flash('Facebook account email not available. Please ensure your Facebook account has a verified email.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email).first()
        
        picture_url = None
        if fb_info.get('picture') and fb_info['picture'].get('data'):
            picture_url = fb_info['picture']['data'].get('url')
        
        if user:
            user.replit_id = f'facebook_{fb_id}'
            if picture_url and not user.profile_image_url:
                user.profile_image_url = picture_url
        else:
            user = User(
                email=email,
                first_name=fb_info.get('first_name', 'User'),
                last_name=fb_info.get('last_name', ''),
                replit_id=f'facebook_{fb_id}',
                profile_image_url=picture_url,
                specialty='',
                medical_license=f'FACEBOOK-{fb_id}',
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user)
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        logging.error(f"Facebook OAuth error: {str(e)}")
        flash('An error occurred during Facebook login.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/facebook/data-deletion', methods=['POST'])
def facebook_data_deletion():
    """
    Facebook Data Deletion Callback
    Required by Facebook for GDPR/privacy compliance
    """
    import json
    import base64
    import hashlib
    import hmac
    
    try:
        signed_request = request.form.get('signed_request')
        if not signed_request:
            return json.dumps({'error': 'Missing signed_request'}), 400
        
        # Parse the signed request
        parts = signed_request.split('.')
        if len(parts) != 2:
            return json.dumps({'error': 'Invalid signed_request format'}), 400
        
        encoded_sig, payload = parts
        
        # Decode the payload
        payload += '=' * (4 - len(payload) % 4)  # Add padding
        decoded_payload = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded_payload)
        
        # Verify signature
        secret = FACEBOOK_APP_SECRET
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        encoded_sig += '=' * (4 - len(encoded_sig) % 4)
        decoded_sig = base64.urlsafe_b64decode(encoded_sig)
        
        if not hmac.compare_digest(decoded_sig, expected_sig):
            logging.warning("Facebook data deletion: Invalid signature")
            return json.dumps({'error': 'Invalid signature'}), 403
        
        # Get the Facebook user ID
        fb_user_id = data.get('user_id')
        
        if fb_user_id:
            # Find and delete user data associated with this Facebook ID
            user = User.query.filter(User.replit_id == f'facebook_{fb_user_id}').first()
            if user:
                # Generate a confirmation code
                confirmation_code = secrets.token_hex(8).upper()
                
                # Log the deletion request
                logging.info(f"Facebook data deletion request for user: {user.email}, FB ID: {fb_user_id}")
                
                # Delete the user (or anonymize - depending on your policy)
                # For now, we'll anonymize the Facebook connection
                user.replit_id = None
                user.profile_image_url = None
                db.session.commit()
                
                # Return confirmation as required by Facebook
                return json.dumps({
                    'url': f'https://medmoneyincubator.com/auth/facebook/deletion-status?code={confirmation_code}',
                    'confirmation_code': confirmation_code
                })
        
        # No user found, but still return success
        return json.dumps({
            'url': 'https://medmoneyincubator.com/privacy',
            'confirmation_code': 'NO_DATA_FOUND'
        })
        
    except Exception as e:
        logging.error(f"Facebook data deletion error: {str(e)}")
        return json.dumps({'error': 'Internal error'}), 500


@auth_bp.route('/facebook/deletion-status')
def facebook_deletion_status():
    """Show status of Facebook data deletion request"""
    code = request.args.get('code', '')
    return render_template('auth/deletion_status.html', confirmation_code=code)


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


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset email"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            token = user.generate_password_reset_token()
            db.session.commit()
            
            # Send reset email
            from mailer import send_email
            
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">MedInvest</h1>
                </div>
                <div style="padding: 30px; background: #f8fafc;">
                    <h2 style="color: #1e293b;">Password Reset Request</h2>
                    <p style="color: #475569; line-height: 1.6;">
                        Hi {user.first_name},
                    </p>
                    <p style="color: #475569; line-height: 1.6;">
                        We received a request to reset your password. Click the button below to create a new password:
                    </p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" 
                           style="background: #2563eb; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 8px; font-weight: bold;
                                  display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    <p style="color: #475569; line-height: 1.6; font-size: 14px;">
                        This link will expire in 1 hour. If you didn't request this reset, 
                        you can safely ignore this email.
                    </p>
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <a href="{reset_url}" style="color: #2563eb;">{reset_url}</a>
                    </p>
                </div>
                <div style="background: #1e293b; padding: 20px; text-align: center;">
                    <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                        MedInvest - Investment Education for Medical Professionals
                    </p>
                </div>
            </div>
            """
            
            email_sent = send_email(
                to_email=user.email,
                subject='Reset Your MedInvest Password',
                html_content=html_content,
                text_content=f"Reset your password: {reset_url}"
            )
            
            if email_sent:
                logging.info(f"Password reset email sent to {user.email}")
            else:
                logging.warning(f"Failed to send password reset email to {user.email}")
        else:
            logging.info(f"Password reset requested for non-existent email: {email}")
        
        # Always show success message to prevent email enumeration
        flash('If an account exists with that email, you will receive password reset instructions.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    
    # Find user with this token
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        # Update password and clear token
        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        
        flash('Your password has been reset successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback - custom implementation with explicit redirect_uri"""
    import requests
    
    # Verify state to prevent CSRF
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    
    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check for errors from Google
    error = request.args.get('error')
    if error:
        logging.error(f"Google OAuth error: {error}")
        flash('Google login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get the authorization code
    code = request.args.get('code')
    if not code:
        flash('No authorization code received from Google.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Exchange code for tokens using explicit redirect_uri
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,  # Must match exactly what was sent in auth request
            'grant_type': 'authorization_code'
        }
        
        logging.info(f"Exchanging code for tokens with redirect_uri: {GOOGLE_REDIRECT_URI}")
        token_response = requests.post(token_url, data=token_data)
        
        if not token_response.ok:
            logging.error(f"Token exchange failed: {token_response.text}")
            flash('Failed to authenticate with Google.', 'error')
            return redirect(url_for('auth.login'))
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        
        if not access_token:
            flash('No access token received from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        # Get user info using the access token
        userinfo_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if not userinfo_response.ok:
            flash('Failed to get user info from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        google_info = userinfo_response.json()
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
        logging.error(f"Google OAuth error: {str(e)}")
        flash('An error occurred during Google login.', 'error')
        return redirect(url_for('auth.login'))



# Physician Verification Routes
ALLOWED_DOCUMENT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_document_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS


@auth_bp.route('/verify')
@login_required
def verify_physician():
    """Physician verification page"""
    show_code_form = bool(current_user.professional_email and 
                          current_user.professional_email_code and 
                          not current_user.professional_email_verified)
    return render_template('verification.html', show_code_form=show_code_form)


@auth_bp.route('/verify/email', methods=['POST'])
@login_required
def send_verification_email():
    """Send verification code to professional email"""
    email = request.form.get('email', '').strip().lower()
    
    if not email:
        flash('Please enter an email address', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Extract domain from email
    if '@' not in email:
        flash('Please enter a valid email address', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    domain = email.split('@')[1].lower()
    
    # Allowed domain suffixes (must end with these)
    allowed_suffixes = ['.edu', '.gov']
    
    # Specific allowed hospital/healthcare domains
    allowed_domains = [
        'kp.org', 'mayoclinic.org', 'clevelandclinic.org', 'cedars-sinai.org',
        'upmc.edu', 'jhmi.edu', 'stanford.edu', 'harvard.edu', 'yale.edu',
        'columbia.edu', 'ucsf.edu', 'ucla.edu', 'ucsd.edu', 'upenn.edu',
        'northwestern.edu', 'duke.edu', 'emory.edu', 'unc.edu', 'osu.edu',
        'memorialhealth.com', 'hcahealthcare.com', 'commonspirit.org',
        'ascension.org', 'dignityhealth.org', 'sutter.org', 'providence.org',
        'trinityhealthmichigan.org', 'beaumont.org', 'nhs.uk', 'nhs.net'
    ]
    
    is_institutional = (
        any(domain.endswith(suffix) for suffix in allowed_suffixes) or
        domain in allowed_domains or
        domain.endswith('.hospital.org') or
        domain.endswith('.medcenter.org')
    )
    
    if not is_institutional:
        flash('Please use an institutional email (.edu, .gov) or recognized hospital domain (e.g., @ucsf.edu, @kp.org)', 'warning')
        return redirect(url_for('auth.verify_physician'))
    
    # Generate 6-digit code
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Store code and email
    current_user.professional_email = email
    current_user.professional_email_code = code
    current_user.professional_email_code_expires = datetime.utcnow() + timedelta(minutes=30)
    db.session.commit()
    
    # Send verification email
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a73e8;">MedInvest Email Verification</h2>
        <p>Hello,</p>
        <p>Your verification code is:</p>
        <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 32px; letter-spacing: 8px; font-weight: bold; margin: 20px 0;">
            {code}
        </div>
        <p>This code will expire in 30 minutes.</p>
        <p>If you didn't request this verification, please ignore this email.</p>
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            MedInvest - Investment Education for Medical Professionals
        </p>
    </div>
    """
    
    success = send_email(email, 'MedInvest - Verify Your Professional Email', html_content)
    
    if success:
        flash(f'Verification code sent to {email}. Check your inbox!', 'success')
    else:
        flash('Unable to send verification email. Please try again later.', 'error')
    
    return redirect(url_for('auth.verify_physician'))


@auth_bp.route('/verify/email/code', methods=['POST'])
@login_required
def verify_email_code():
    """Verify the email code"""
    code = request.form.get('code', '').strip()
    
    if not code:
        flash('Please enter the verification code', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    if not current_user.professional_email_code:
        flash('No verification code pending. Please request a new one.', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    if datetime.utcnow() > current_user.professional_email_code_expires:
        flash('Verification code has expired. Please request a new one.', 'error')
        current_user.professional_email_code = None
        db.session.commit()
        return redirect(url_for('auth.verify_physician'))
    
    if code != current_user.professional_email_code:
        flash('Invalid verification code. Please try again.', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Mark email as verified
    current_user.professional_email_verified = True
    current_user.professional_email_code = None
    current_user.professional_email_code_expires = None
    
    # Update overall verification status if both steps complete
    if current_user.license_verified:
        current_user.is_verified = True
        current_user.verification_status = 'verified'
        current_user.verified_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Professional email verified successfully!', 'success')
    return redirect(url_for('auth.verify_physician'))


@auth_bp.route('/verify/license', methods=['POST'])
@login_required
def upload_license():
    """Upload medical license or ID document"""
    if 'license_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    file = request.files['license_file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    if not allowed_document_file(file.filename):
        flash('Invalid file type. Please upload JPG, PNG, or PDF.', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Check file size (max 10MB)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > 10 * 1024 * 1024:
        flash('File too large. Maximum size is 10MB.', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"license_{current_user.id}_{secrets.token_hex(8)}.{ext}"
    
    # Ensure upload directory exists
    upload_dir = os.path.join('media', 'uploads', 'licenses')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filepath = os.path.join(upload_dir, unique_filename)
    file.save(filepath)
    
    # Update user record
    current_user.license_document_url = f"/media/uploads/licenses/{unique_filename}"
    current_user.license_document_uploaded_at = datetime.utcnow()
    current_user.verification_status = 'pending'
    current_user.verification_submitted_at = datetime.utcnow()
    db.session.commit()
    
    flash('License document uploaded successfully! Our team will review it within 1-2 business days.', 'success')
    return redirect(url_for('auth.verify_physician'))
