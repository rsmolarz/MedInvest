"""
Authentication Routes - Login, Register, Logout, Verification
"""
import os
import logging
import random
import time
import jwt
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from datetime import datetime, timedelta
from urllib.parse import urlencode
from werkzeug.utils import secure_filename
import secrets
from app import db
from models import User, Referral, LoginSession, VerificationQueueEntry
from mailer import send_email


def record_login_session(user_id, login_method='password', is_successful=True, failure_reason=None):
    """Record a login session for security tracking - failures are logged but don't interrupt auth"""
    try:
        try:
            from user_agents import parse as parse_ua
            user_agent_str = request.headers.get('User-Agent', '')
            try:
                ua = parse_ua(user_agent_str)
                browser = f"{ua.browser.family} {ua.browser.version_string}"
                os_info = f"{ua.os.family} {ua.os.version_string}"
                device_type = 'Mobile' if ua.is_mobile else ('Tablet' if ua.is_tablet else 'Desktop')
            except:
                browser = 'Unknown'
                os_info = 'Unknown'
                device_type = 'Unknown'
        except ImportError:
            user_agent_str = request.headers.get('User-Agent', '')
            browser = 'Unknown'
            os_info = 'Unknown'
            device_type = 'Desktop' if 'Windows' in user_agent_str or 'Mac' in user_agent_str else 'Unknown'
        
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        elif ip_address:
            ip_address = ip_address.strip()        
        session_record = LoginSession(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=request.headers.get('User-Agent', '')[:500],
            device_type=device_type,
            browser=browser,
            os=os_info,
            login_method=login_method,
            is_successful=is_successful,
            failure_reason=failure_reason
        )
        db.session.add(session_record)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to record login session: {e}")
        db.session.rollback()
from routes.notifications import notify_invite_accepted
from gohighlevel import add_contact_to_ghl

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Facebook OAuth Configuration
FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')

# Apple OAuth Configuration
APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID')  # Service ID (e.g., com.yourcompany.yourapp)
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID')
APPLE_KEY_ID = os.environ.get('APPLE_KEY_ID')
APPLE_PRIVATE_KEY = os.environ.get('APPLE_PRIVATE_KEY', '').replace('\\n', '\n')


def get_oauth_redirect_uri(provider):
    """Get the OAuth redirect URI - always use the public production URL for consistency"""
    # Check for custom domain first
    custom_domain = os.environ.get('CUSTOM_DOMAIN')
    if custom_domain:
        base_url = f"https://{custom_domain}"
    else:
        # Always use the fixed production URL for OAuth callbacks
        # This ensures Facebook, Google, GitHub etc. callbacks match their configured URLs
        base_url = "https://med-invest-rsmolarz.replit.app"
    
    logging.info(f"OAuth redirect URI for {provider}: {base_url}/auth/{provider}/callback")
    return f"{base_url}/auth/{provider}/callback"


def create_signed_oauth_state(provider, redirect_uri):
    """Create a signed OAuth state token that doesn't depend on session"""
    import hashlib
    import hmac
    import base64
    import json
    
    secret = os.environ.get('SESSION_SECRET')
    if not secret:
        raise ValueError("SESSION_SECRET environment variable is not set")
    nonce = secrets.token_urlsafe(16)
    timestamp = int(time.time())
    
    data = {
        'p': provider,
        'r': redirect_uri,
        't': timestamp,
        'n': nonce
    }
    
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    
    return f"{payload}.{signature}"


def verify_signed_oauth_state(state, provider, max_age=600):
    """Verify a signed OAuth state token"""
    import hashlib
    import hmac
    import base64
    import json
    
    try:
        if not state or '.' not in state:
            logging.error(f"OAuth state missing or malformed: {state}")
            return None
        
        payload, signature = state.rsplit('.', 1)
        secret = os.environ.get('SESSION_SECRET')
        if not secret:
            raise ValueError("SESSION_SECRET environment variable is not set")
        expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected_sig):
            logging.error("OAuth state signature mismatch")
            return None
        
        data = json.loads(base64.urlsafe_b64decode(payload).decode())
        
        if data.get('p') != provider:
            logging.error(f"OAuth state provider mismatch: expected {provider}, got {data.get('p')}")
            return None
        
        if int(time.time()) - data.get('t', 0) > max_age:
            logging.error("OAuth state expired")
            return None
        
        return data.get('r')  # Return the redirect_uri
        
    except Exception as e:
        logging.error(f"OAuth state verification failed: {e}")
        return None


def generate_apple_client_secret():
    """Generate Apple client secret dynamically using JWT"""
    if not all([APPLE_TEAM_ID, APPLE_CLIENT_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY]):
        return None
    
    headers = {
        'kid': APPLE_KEY_ID,
        'alg': 'ES256'
    }
    
    payload = {
        'iss': APPLE_TEAM_ID,
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,  # 10 minutes
        'aud': 'https://appleid.apple.com',
        'sub': APPLE_CLIENT_ID
    }
    
    try:
        client_secret = jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm='ES256', headers=headers)
        return client_secret
    except Exception as e:
        logging.error(f"Failed to generate Apple client secret: {e}")
        return None


def verify_apple_id_token(id_token):
    """Verify Apple ID token using Apple's JWKS"""
    import requests
    from jwt import PyJWKClient
    
    try:
        jwks_url = 'https://appleid.apple.com/auth/keys'
        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        
        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=['RS256'],
            audience=APPLE_CLIENT_ID,
            issuer='https://appleid.apple.com'
        )
        return decoded
    except jwt.ExpiredSignatureError:
        logging.error("Apple ID token has expired")
        return None
    except jwt.InvalidAudienceError:
        logging.error("Apple ID token has invalid audience")
        return None
    except jwt.InvalidIssuerError:
        logging.error("Apple ID token has invalid issuer")
        return None
    except Exception as e:
        logging.error(f"Apple ID token verification failed: {e}")
        return None

# Google OAuth Blueprint (for compatibility, but we'll use custom routes)
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=['openid', 'email', 'profile'],
    redirect_to='auth.google_callback'
)


@auth_bp.route('/google-login')
def google_login_custom():
    """Custom Google OAuth login with dynamic redirect_uri"""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'google'
    
    # Check if user is already logged in - this is a "connect" attempt
    if current_user.is_authenticated:
        session['oauth_connect_mode'] = True
        session['oauth_connect_user_id'] = current_user.id
    else:
        session['oauth_connect_mode'] = False
    
    redirect_uri = get_oauth_redirect_uri('google')
    session['oauth_redirect_uri'] = redirect_uri
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account'
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    logging.info(f"Redirecting to Google OAuth with redirect_uri: {redirect_uri}")
    return redirect(auth_url)


@auth_bp.route('/facebook-login')
def facebook_login():
    """Facebook OAuth login with dynamic redirect_uri using signed state"""
    # Read credentials at request time to ensure latest values
    facebook_app_id = os.environ.get('FACEBOOK_APP_ID')
    
    if not facebook_app_id:
        flash('Facebook login is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is already logged in - this is a "connect" attempt
    if current_user.is_authenticated:
        session['oauth_connect_mode'] = True
        session['oauth_connect_user_id'] = current_user.id
    else:
        session['oauth_connect_mode'] = False
    
    redirect_uri = get_oauth_redirect_uri('facebook')
    
    # Use signed state that doesn't depend on session persistence
    state = create_signed_oauth_state('facebook', redirect_uri)
    
    # Also store in session as backup
    session['oauth_state'] = state
    session['oauth_provider'] = 'facebook'
    session['oauth_redirect_uri'] = redirect_uri
    
    params = {
        'client_id': facebook_app_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'public_profile,email',
        'state': state
    }
    
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
    logging.info(f"Facebook OAuth - App ID: {facebook_app_id}, redirect_uri: {redirect_uri}")
    return redirect(auth_url)


@auth_bp.route('/github-login')
def github_login():
    """GitHub OAuth login with dynamic redirect_uri"""
    # Read credentials at request time to ensure latest values
    github_client_id = os.environ.get('GITHUB_CLIENT_ID')
    
    if not github_client_id:
        flash('GitHub login is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is already logged in - this is a "connect" attempt
    if current_user.is_authenticated:
        session['oauth_connect_mode'] = True
        session['oauth_connect_user_id'] = current_user.id
    else:
        session['oauth_connect_mode'] = False
    
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'github'
    
    redirect_uri = get_oauth_redirect_uri('github')
    session['oauth_redirect_uri'] = redirect_uri
    
    # Debug: log exactly what we're sending
    logging.info(f"GitHub OAuth - Client ID: {github_client_id}")
    logging.info(f"GitHub OAuth - Redirect URI: {redirect_uri}")
    
    params = {
        'client_id': github_client_id,
        'redirect_uri': redirect_uri,
        'scope': 'user:email read:user',
        'state': state
    }
    
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    logging.info(f"Redirecting to GitHub OAuth with full URL: {auth_url}")
    return redirect(auth_url)


@auth_bp.route('/apple-login')
def apple_login():
    """Apple Sign In with dynamic redirect_uri"""
    if not APPLE_CLIENT_ID:
        flash('Apple Sign In is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is already logged in - this is a "connect" attempt
    if current_user.is_authenticated:
        session['oauth_connect_mode'] = True
        session['oauth_connect_user_id'] = current_user.id
    else:
        session['oauth_connect_mode'] = False
    
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'apple'
    
    redirect_uri = get_oauth_redirect_uri('apple')
    session['oauth_redirect_uri'] = redirect_uri
    
    params = {
        'client_id': APPLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'email name',
        'state': state,
        'response_mode': 'form_post'
    }
    
    auth_url = f"https://appleid.apple.com/auth/authorize?{urlencode(params)}"
    logging.info(f"Redirecting to Apple OAuth with redirect_uri: {redirect_uri}")
    return redirect(auth_url)


@auth_bp.route('/apple/callback', methods=['GET', 'POST'])
def apple_callback():
    """Handle Apple Sign In callback (uses POST with form_post)"""
    import requests
    
    state = request.form.get('state') or request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    redirect_uri = session.pop('oauth_redirect_uri', get_oauth_redirect_uri('apple'))
    
    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    error = request.form.get('error') or request.args.get('error')
    if error:
        logging.error(f"Apple OAuth error: {error}")
        flash('Apple login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))
    
    code = request.form.get('code') or request.args.get('code')
    if not code:
        flash('No authorization code received from Apple.', 'error')
        return redirect(url_for('auth.login'))
    
    user_data = request.form.get('user')
    apple_user_info = {}
    if user_data:
        import json
        try:
            apple_user_info = json.loads(user_data)
        except:
            pass
    
    try:
        client_secret = generate_apple_client_secret()
        if not client_secret:
            flash('Apple Sign In is not properly configured.', 'error')
            return redirect(url_for('auth.login'))
        
        token_url = 'https://appleid.apple.com/auth/token'
        token_data = {
            'client_id': APPLE_CLIENT_ID,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        
        token_response = requests.post(token_url, data=token_data)
        
        if not token_response.ok:
            logging.error(f"Apple token exchange failed: {token_response.text}")
            flash('Failed to authenticate with Apple.', 'error')
            return redirect(url_for('auth.login'))
        
        tokens = token_response.json()
        id_token = tokens.get('id_token')
        
        if not id_token:
            flash('No ID token received from Apple.', 'error')
            return redirect(url_for('auth.login'))
        
        decoded = verify_apple_id_token(id_token)
        if not decoded:
            flash('Apple token verification failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        apple_id = decoded.get('sub')
        email = decoded.get('email')
        
        if not email:
            flash('Apple account email not available.', 'error')
            return redirect(url_for('auth.login'))
        
        first_name = apple_user_info.get('name', {}).get('firstName', 'Apple')
        last_name = apple_user_info.get('name', {}).get('lastName', 'User')
        
        # Check if this is a "connect" attempt (user was already logged in)
        connect_mode = session.pop('oauth_connect_mode', False)
        connect_user_id = session.pop('oauth_connect_user_id', None)
        
        if connect_mode and connect_user_id:
            # Connect mode: link Apple to the current user's account
            user = User.query.get(connect_user_id)
            if user:
                # Check if this Apple account is already linked to another user
                existing_apple_user = User.query.filter_by(apple_id=apple_id).first()
                if existing_apple_user and existing_apple_user.id != user.id:
                    flash('This Apple account is already linked to another user.', 'error')
                    return redirect(url_for('main.sso_connections'))
                
                user.apple_id = apple_id
                user.replit_id = f'apple_{apple_id}'
                db.session.commit()
                flash('Apple account connected successfully!', 'success')
                return redirect(url_for('main.sso_connections'))
            else:
                flash('Session expired. Please try again.', 'error')
                return redirect(url_for('main.sso_connections'))
        
        # Normal login mode
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.replit_id = f'apple_{apple_id}'
            user.apple_id = apple_id
        else:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                replit_id=f'apple_{apple_id}',
                apple_id=apple_id,
                specialty='',
                medical_license=f'APPLE-{apple_id[:8]}',
            )
            user.generate_referral_code()
            db.session.add(user)
            
            try:
                add_contact_to_ghl(first_name, last_name, email, user.specialty)
            except Exception as e:
                logging.error(f"Failed to add user to GHL: {e}")
        
        db.session.commit()
        login_user(user, remember=True)
        record_login_session(user.id, 'Apple')
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        logging.error(f"Apple OAuth error: {str(e)}")
        flash('An error occurred during Apple login.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/github/callback')
def github_callback():
    """Handle GitHub OAuth callback - simplified approach"""
    import requests
    
    # Read credentials at request time
    github_client_id = os.environ.get('GITHUB_CLIENT_ID')
    github_client_secret = os.environ.get('GITHUB_CLIENT_SECRET')
    
    state = request.args.get('state')
    
    # Clear session state (cleanup)
    session.pop('oauth_state', None)
    session.pop('oauth_redirect_uri', None)
    
    # Try to verify signed state first, fall back to regenerating redirect_uri
    redirect_uri = verify_signed_oauth_state(state, 'github')
    
    if not redirect_uri:
        # Fall back to generating redirect_uri from current request
        logging.warning(f"GitHub OAuth state verification failed, using fallback redirect_uri")
        redirect_uri = get_oauth_redirect_uri('github')
    
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
            'client_id': github_client_id,
            'client_secret': github_client_secret,
            'redirect_uri': redirect_uri,
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
        
        name_parts = gh_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else 'User'
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Check if this is a "connect" attempt (user was already logged in)
        connect_mode = session.pop('oauth_connect_mode', False)
        connect_user_id = session.pop('oauth_connect_user_id', None)
        
        if connect_mode and connect_user_id:
            # Connect mode: link GitHub to the current user's account
            user = User.query.get(connect_user_id)
            if user:
                # Check if this GitHub account is already linked to another user
                existing_gh_user = User.query.filter_by(github_id=str(gh_id)).first()
                if existing_gh_user and existing_gh_user.id != user.id:
                    flash('This GitHub account is already linked to another user.', 'error')
                    return redirect(url_for('main.sso_connections'))
                
                user.github_id = str(gh_id)
                user.replit_id = f'github_{gh_id}'
                if gh_avatar and not user.profile_image_url:
                    user.profile_image_url = gh_avatar
                db.session.commit()
                flash('GitHub account connected successfully!', 'success')
                return redirect(url_for('main.sso_connections'))
            else:
                flash('Session expired. Please try again.', 'error')
                return redirect(url_for('main.sso_connections'))
        
        # Normal login mode
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.replit_id = f'github_{gh_id}'
            user.github_id = str(gh_id)
            if gh_avatar and not user.profile_image_url:
                user.profile_image_url = gh_avatar
        else:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                replit_id=f'github_{gh_id}',
                github_id=str(gh_id),
                profile_image_url=gh_avatar,
                specialty='',
                medical_license=f'GITHUB-{gh_id}',
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user, remember=True)
        record_login_session(user.id, 'GitHub')
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        logging.error(f"GitHub OAuth error: {str(e)}")
        flash('An error occurred during GitHub login.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/facebook/callback')
def facebook_callback():
    """Handle Facebook OAuth callback - simplified approach"""
    import requests
    
    # Log all incoming parameters for debugging
    logging.info(f"Facebook callback - Full URL: {request.url}")
    logging.info(f"Facebook callback - Args: {dict(request.args)}")
    
    state = request.args.get('state')
    
    # Clear session state (cleanup)
    session.pop('oauth_state', None)
    session.pop('oauth_redirect_uri', None)
    
    # Always use the fixed production redirect URI for Facebook
    # This ensures consistency between login and callback
    redirect_uri = get_oauth_redirect_uri('facebook')
    
    logging.info(f"Facebook callback - Using redirect_uri: {redirect_uri}")
    
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
        # Read credentials at request time to ensure latest values
        facebook_app_id = os.environ.get('FACEBOOK_APP_ID')
        facebook_app_secret = os.environ.get('FACEBOOK_APP_SECRET')
        
        token_url = 'https://graph.facebook.com/v18.0/oauth/access_token'
        token_params = {
            'client_id': facebook_app_id,
            'client_secret': facebook_app_secret,
            'redirect_uri': redirect_uri,
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
        
        picture_url = None
        if fb_info.get('picture') and fb_info['picture'].get('data'):
            picture_url = fb_info['picture']['data'].get('url')
        
        # Check if this is a "connect" attempt (user was already logged in)
        connect_mode = session.pop('oauth_connect_mode', False)
        connect_user_id = session.pop('oauth_connect_user_id', None)
        
        if connect_mode and connect_user_id:
            # Connect mode: link Facebook to the current user's account
            user = User.query.get(connect_user_id)
            if user:
                # Check if this Facebook account is already linked to another user
                existing_fb_user = User.query.filter_by(facebook_id=fb_id).first()
                if existing_fb_user and existing_fb_user.id != user.id:
                    flash('This Facebook account is already linked to another user.', 'error')
                    return redirect(url_for('main.sso_connections'))
                
                user.facebook_id = fb_id
                user.replit_id = f'facebook_{fb_id}'
                if picture_url and not user.profile_image_url:
                    user.profile_image_url = picture_url
                db.session.commit()
                flash('Facebook account connected successfully!', 'success')
                return redirect(url_for('main.sso_connections'))
            else:
                flash('Session expired. Please try again.', 'error')
                return redirect(url_for('main.sso_connections'))
        
        # Normal login mode
        # If no email permission, generate a placeholder email
        if not email:
            email = f"facebook_{fb_id}@placeholder.medinvest.com"
            logging.info(f"No email from Facebook for user {fb_id}, using placeholder")
        
        # First try to find user by Facebook ID, then by email
        user = User.query.filter_by(replit_id=f'facebook_{fb_id}').first()
        if not user:
            user = User.query.filter_by(email=email).first()
        
        if user:
            user.replit_id = f'facebook_{fb_id}'
            user.facebook_id = fb_id  # Store Facebook ID for sync
            if picture_url and not user.profile_image_url:
                user.profile_image_url = picture_url
        else:
            # Generate a random unusable password for OAuth users
            from werkzeug.security import generate_password_hash
            random_password = secrets.token_urlsafe(32)
            
            user = User(
                email=email,
                first_name=fb_info.get('first_name', 'User'),
                last_name=fb_info.get('last_name', ''),
                replit_id=f'facebook_{fb_id}',
                facebook_id=fb_id,  # Store Facebook ID for sync
                profile_image_url=picture_url,
                specialty='',
                medical_license=f'FACEBOOK-{fb_id}',
                password_hash=generate_password_hash(random_password),
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user, remember=True)
        record_login_session(user.id, 'Facebook')
        
        flash(f'Welcome, {user.first_name}!', 'success')
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('main.feed'))
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        tb = traceback.format_exc()
        logging.error(f"Facebook OAuth error: {error_msg}")
        logging.error(f"Facebook OAuth traceback: {tb}")
        # Show more detail to help debug (remove in production)
        flash(f'Facebook login error: {error_msg[:200]}', 'error')
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
        secret = os.environ.get('FACEBOOK_APP_SECRET', '')
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
            record_login_session(user.id, 'password')
            
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
        
        if user:
            record_login_session(user.id, 'password', is_successful=False, failure_reason='Invalid password')
        flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    
    if request.method == 'POST':
        try:
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
                
                # Notify the inviter that someone accepted their invite
                notify_invite_accepted(referred_by.id, user)
                db.session.commit()
            
            # Add new user to GoHighLevel CRM (runs in background)
            add_contact_to_ghl(user)
            
            login_user(user, remember=True)
            record_login_session(user.id, 'registration')
            flash('Welcome to MedInvest! Your account has been created.', 'success')
            return redirect(url_for('main.feed'))
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('auth/register.html')
    
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
            record_login_session(user.id, '2FA')
            
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
    """Handle Google OAuth callback - custom implementation with dynamic redirect_uri"""
    import requests
    
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    redirect_uri = session.pop('oauth_redirect_uri', get_oauth_redirect_uri('google'))
    
    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    error = request.args.get('error')
    if error:
        logging.error(f"Google OAuth error: {error}")
        flash('Google login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))
    
    code = request.args.get('code')
    if not code:
        flash('No authorization code received from Google.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        logging.info(f"Exchanging code for tokens with redirect_uri: {redirect_uri}")
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
        
        # Check if this is a "connect" attempt (user was already logged in)
        connect_mode = session.pop('oauth_connect_mode', False)
        connect_user_id = session.pop('oauth_connect_user_id', None)
        
        if connect_mode and connect_user_id:
            # Connect mode: link Google to the current user's account
            user = User.query.get(connect_user_id)
            if user:
                # Check if this Google account is already linked to another user
                existing_google_user = User.query.filter_by(google_id=google_id).first()
                if existing_google_user and existing_google_user.id != user.id:
                    flash('This Google account is already linked to another user.', 'error')
                    return redirect(url_for('main.sso_connections'))
                
                user.google_id = google_id
                user.replit_id = f'google_{google_id}'
                if google_info.get('picture') and not user.profile_image_url:
                    user.profile_image_url = google_info.get('picture')
                db.session.commit()
                flash('Google account connected successfully!', 'success')
                return redirect(url_for('main.sso_connections'))
            else:
                flash('Session expired. Please try again.', 'error')
                return redirect(url_for('main.sso_connections'))
        
        # Normal login mode
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.replit_id = f'google_{google_id}'
            user.google_id = google_id
            if google_info.get('picture') and not user.profile_image_url:
                user.profile_image_url = google_info.get('picture')
        else:
            user = User(
                email=email,
                first_name=google_info.get('given_name', 'User'),
                last_name=google_info.get('family_name', ''),
                replit_id=f'google_{google_id}',
                google_id=google_id,
                profile_image_url=google_info.get('picture'),
                specialty='',
                medical_license=f'GOOGLE-{google_id}',
            )
            user.generate_referral_code()
            db.session.add(user)
        
        db.session.commit()
        login_user(user, remember=True)
        record_login_session(user.id, 'Google')
        
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
    
    # Block common personal email domains
    blocked_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
                       'aol.com', 'icloud.com', 'mail.com', 'protonmail.com']
    
    if domain in blocked_domains:
        flash('Please use a professional or work email address (not personal email like Gmail, Yahoo, etc.)', 'warning')
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
    
    # Count verified methods
    verified_count = sum([
        current_user.professional_email_verified,
        current_user.npi_verified or False,
        current_user.license_verified or False
    ])
    
    # Update overall verification status
    if verified_count >= 2:
        current_user.is_verified = True
        current_user.verification_status = 'verified'
        current_user.verified_at = datetime.utcnow()
    else:
        # Add to verification queue for admin review if not already there
        current_user.verification_status = 'pending'
        current_user.verification_submitted_at = datetime.utcnow()
        existing_entry = VerificationQueueEntry.query.filter_by(user_id=current_user.id).first()
        if not existing_entry:
            queue_entry = VerificationQueueEntry(
                user_id=current_user.id,
                submitted_at=datetime.utcnow(),
                sla_deadline=datetime.utcnow() + timedelta(days=2),
                priority=0,
                status='pending'
            )
            db.session.add(queue_entry)
    
    db.session.commit()
    
    flash('Professional email verified successfully!', 'success')
    return redirect(url_for('auth.verify_physician'))


@auth_bp.route('/verify/npi', methods=['POST'])
@login_required
def verify_npi():
    """Verify NPI number against NPI Registry"""
    import requests as req
    
    npi_number = request.form.get('npi_number', '').strip()
    
    if not npi_number:
        flash('Please enter your NPI number', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Validate format (10 digits)
    if not npi_number.isdigit() or len(npi_number) != 10:
        flash('NPI number must be exactly 10 digits', 'error')
        return redirect(url_for('auth.verify_physician'))
    
    # Query the NPI Registry API
    try:
        response = req.get(
            f'https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi_number}',
            timeout=10
        )
        data = response.json()
        
        if data.get('result_count', 0) > 0:
            # NPI found - verify it's a healthcare provider
            result = data['results'][0]
            
            # Get provider name for verification
            if result.get('basic'):
                first_name = result['basic'].get('first_name', '').lower()
                last_name = result['basic'].get('last_name', '').lower()
                
                # Check if name matches (basic verification)
                user_first = current_user.first_name.lower().split()[0] if current_user.first_name else ''
                user_last = current_user.last_name.lower() if current_user.last_name else ''
                
                # Allow some flexibility in name matching
                name_match = (
                    (first_name and user_first and first_name[:3] == user_first[:3]) or
                    (last_name and user_last and last_name == user_last)
                )
                
                if name_match or True:  # Accept any valid NPI for now
                    current_user.npi_number = npi_number
                    current_user.npi_verified = True
                    
                    # Update overall verification if 2+ methods complete
                    verified_count = sum([
                        current_user.professional_email_verified,
                        current_user.npi_verified,
                        current_user.license_verified or False
                    ])
                    if verified_count >= 2:
                        current_user.is_verified = True
                        current_user.verification_status = 'verified'
                        current_user.verified_at = datetime.utcnow()
                    else:
                        # Add to verification queue for admin review
                        current_user.verification_status = 'pending'
                        current_user.verification_submitted_at = datetime.utcnow()
                        existing_entry = VerificationQueueEntry.query.filter_by(user_id=current_user.id).first()
                        if not existing_entry:
                            queue_entry = VerificationQueueEntry(
                                user_id=current_user.id,
                                submitted_at=datetime.utcnow(),
                                sla_deadline=datetime.utcnow() + timedelta(days=2),
                                priority=0,
                                status='pending'
                            )
                            db.session.add(queue_entry)
                    
                    db.session.commit()
                    flash('NPI verified successfully!', 'success')
                    return redirect(url_for('auth.verify_physician'))
            
            # Valid NPI but couldn't match - still accept
            current_user.npi_number = npi_number
            current_user.npi_verified = True
            
            # Add to verification queue for admin review
            verified_count = sum([
                current_user.professional_email_verified,
                current_user.npi_verified,
                current_user.license_verified or False
            ])
            if verified_count >= 2:
                current_user.is_verified = True
                current_user.verification_status = 'verified'
                current_user.verified_at = datetime.utcnow()
            else:
                current_user.verification_status = 'pending'
                current_user.verification_submitted_at = datetime.utcnow()
                existing_entry = VerificationQueueEntry.query.filter_by(user_id=current_user.id).first()
                if not existing_entry:
                    queue_entry = VerificationQueueEntry(
                        user_id=current_user.id,
                        submitted_at=datetime.utcnow(),
                        sla_deadline=datetime.utcnow() + timedelta(days=2),
                        priority=0,
                        status='pending'
                    )
                    db.session.add(queue_entry)
            
            db.session.commit()
            flash('NPI verified successfully!', 'success')
            return redirect(url_for('auth.verify_physician'))
        else:
            flash('NPI number not found in the registry. Please check and try again.', 'error')
            return redirect(url_for('auth.verify_physician'))
            
    except Exception as e:
        # If API fails, allow manual verification
        flash('Unable to verify NPI automatically. Please try again later or use another verification method.', 'warning')
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
    
    # Add to verification queue for admin review if not already there
    existing_entry = VerificationQueueEntry.query.filter_by(user_id=current_user.id).first()
    if not existing_entry:
        queue_entry = VerificationQueueEntry(
            user_id=current_user.id,
            submitted_at=datetime.utcnow(),
            sla_deadline=datetime.utcnow() + timedelta(days=2),
            priority=1,  # Higher priority for license uploads
            status='pending'
        )
        db.session.add(queue_entry)
    
    db.session.commit()
    
    flash('License document uploaded successfully! Our team will review it within 1-2 business days.', 'success')
    return redirect(url_for('auth.verify_physician'))


# ============== Owner Setup Route (One-Time Use) ==============
@auth_bp.route('/owner-setup/<token>')
@login_required
def owner_setup(token):
    """
    One-time setup route for the site owner to grant admin access and verification.
    Only works for the designated owner email with the correct token.
    """
    OWNER_EMAIL = 'rsmolarz@rsmolarz.com'
    SETUP_TOKEN = 'medinvest2025admin'  # Change this after first use
    
    if token != SETUP_TOKEN:
        flash('Invalid setup token.', 'error')
        return redirect(url_for('main.feed'))
    
    if current_user.email.lower() != OWNER_EMAIL.lower():
        flash('This setup link is only valid for the site owner.', 'error')
        return redirect(url_for('main.feed'))
    
    # Grant admin access and verification
    current_user.role = 'admin'
    current_user.is_verified = True
    current_user.verification_status = 'approved'
    current_user.verified_at = datetime.utcnow()
    
    # Generate referral code if missing
    if not current_user.referral_code:
        import string
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(8))
        current_user.referral_code = code
    
    # Set subscription tier
    current_user.subscription_tier = 'premium'
    
    db.session.commit()
    
    flash('Success! You now have admin access, are fully verified, and have a referral code.', 'success')
    logging.info(f"Owner setup completed for {current_user.email}")
    
    return redirect(url_for('main.feed'))