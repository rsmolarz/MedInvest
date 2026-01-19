
"""""
Facebook Page Integration for MedInvest
Posts deals, investment updates, and community news to Facebook page
"""

import os
import requests
import logging
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class FacebookPageIntegration:
        """Handle all Facebook page posting operations"""
        
        def __init__(self):
                    self.page_access_token = os.environ.get('FACEBOOK_PAGE_ACCESS_TOKEN')
                    self.page_id = os.environ.get('FACEBOOK_PAGE_ID')
                    self.app_id = os.environ.get('FACEBOOK_APP_ID')
                    self.app_secret = os.environ.get('FACEBOOK_APP_SECRET')
                    self.base_url = "https://graph.facebook.com/v18.0"
                    
                    if not self.page_access_token or not self.page_id:
                                    logger.warning("Facebook credentials not configured. Facebook integration disabled.")
                            
                def post_deal(self, deal: Dict) -> Optional[str]:
                            """
                                    Post a new investment deal to Facebook page
                                            
                                                    Args:
                                                                deal: Dictionary containing deal information
                                                                                {
                                                                                                    'id': int,
                                                                                                                        'title': str,
                                                                                                                                            'description': str,
                                                                                                                                                                'funding_goal': float,
                                                                                                                                                                                    'company': str,
                                                                                                                                                                                                        'image_url': str (optional),
                                                                                                                                                                                                                            'deal_url': str (optional)
                                                                                                                                                                                                                                            }
                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                            Returns:
                                                                                                                                                                                                                                                                        Facebook post ID if successful, None otherwise
                                                                                                                                                                                                                                                                                """
                            if not self.page_access_token:
                                            logger.error("Facebook page access token not configured")
                                            return None
                                        
                            try:
                                            # Build message
                                            message = f"""🏥 New Healthcare Investment Opportunity! 
                                            
                                            {deal.get('title', 'Investment Deal')}
                                            
                                            Company: {deal.get('company', 'N/A')}
                                            Funding Goal: ${deal.get('funding_goal', 0):,.0f}
                                            
                                            {deal.get('description', '')[:200]}...
                                            
                                            Join our community to learn more and invest in healthcare innovation!
                                            MedInvest - Where Physicians Invest
                                            
                                            #Healthcare #Investment #MedInvest #Medical Innovation"""
                                
                                payload = {
                                                    'message': message,
                                                    'access_token': self.page_access_token
                                }
            
            # Add image if available
            if deal.get('image_url'):
                                payload['link'] = deal.get('deal_url', 'https://medmoneyincubator.com')
                                payload['picture'] = deal.get('image_url')
                            
            url = f"{self.base_url}/{self.page_id}/feed"
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                                post_id = response.json().get('id')
                                logger.info(f"Successfully posted deal to Facebook: {post_id}")
                                return post_id
            else:
                                logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                                return None
                                
except Exception as e:
            logger.error(f"Error posting deal to Facebook: {str(e)}")
            return None
    
    def post_milestone(self, milestone: Dict) -> Optional[str]:
                """
                        Post a deal milestone (e.g., 50% funded) to Facebook
                                
                                        Args:
                                                    milestone: Dictionary with milestone info
                                                                    {
                                                                                        'deal_id': int,
                                                                                                            'deal_title': str,
                                                                                                                                'funding_percentage': float,
                                                                                                                                                    'funded_amount': float,
                                                                                                                                                                        'goal_amount': float
                                                                                                                                                                                        }
                                                                                                                                                                                                
                                                                                                                                                                                                        Returns:
                                                                                                                                                                                                                    Facebook post ID if successful, None otherwise
                                                                                                                                                                                                                            """
                if not self.page_access_token:
                                logger.error("Facebook page access token not configured")
                                return None
                            
                try:
                                message = f"""🎉 Deal Milestone Update! 
                                
                                {milestone.get('deal_title', 'Investment Deal')} has reached {milestone.get('funding_percentage', 0):.0f}% funding!
                                
                                ${milestone.get('funded_amount', 0):,.0f} of ${milestone.get('goal_amount', 0):,.0f} raised
                                
                                This shows strong investor confidence in healthcare innovation!
                                
                                Join the growing community of healthcare professionals investing in the future.
                                
                                #Healthcare #Investment #MedInvest"""
                    
                    payload = {
                                        'message': message,
                                        'access_token': self.page_access_token
                    }
            
            url = f"{self.base_url}/{self.page_id}/feed"
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                                post_id = response.json().get('id')
                                logger.info(f"Successfully posted milestone to Facebook: {post_id}")
                                return post_id
            else:
                                logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                                return None
                                
except Exception as e:
            logger.error(f"Error posting milestone to Facebook: {str(e)}")
            return None
    
    def post_community_update(self, update: Dict) -> Optional[str]:
                """
                        Post a community update or announcement
                                
                                        Args:
                                                    update: Dictionary with update info
                                                                    {
                                                                                        'title': str,
                                                                                                            'content': str,
                                                                                                                                'image_url': str (optional),
                                                                                                                                                    'link': str (optional)
                                                                                                                                                                    }
                                                                                                                                                                            
                                                                                                                                                                                    Returns:
                                                                                                                                                                                                Facebook post ID if successful, None otherwise
                                                                                                                                                                                                        """
                if not self.page_access_token:
                                logger.error("Facebook page access token not configured")
                                return None
                            
                try:
                                message = f"""{update.get('title', 'Community Update')}
                                
                                {update.get('content', '')}
                                
                                Stay tuned for more healthcare investment insights from the MedInvest community!
                                
                                #Healthcare #Investment #MedInvest"""
                    
                    payload = {
                                        'message': message,
                                        'access_token': self.page_access_token
                    }
            
            if update.get('link'):
                                payload['link'] = update.get('link')
                            
            url = f"{self.base_url}/{self.page_id}/feed"
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                                post_id = response.json().get('id')
                                logger.info(f"Successfully posted community update to Facebook: {post_id}")
                                return post_id
            else:
                                logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                                return None
                                
except Exception as e:
            logger.error(f"Error posting community update to Facebook: {str(e)}")
            return None
    
    def get_page_insights(self, metric: str = 'page_fans') -> Optional[Dict]:
                """
                        Get Facebook page insights (followers, engagement, etc)
                                
                                        Args:
                                                    metric: Metric to retrieve (page_fans, page_engaged_users, etc)
                                                            
                                                                    Returns:
                                                                                Insights data if successful, None otherwise
                                                                                        """
                if not self.page_access_token:
                                logger.error("Facebook page access token not configured")
                                return None
                            
                try:
                                url = f"{self.base_url}/{self.page_id}/insights/{metric}"
                                params = {'access_token': self.page_access_token}
                                
                                response = requests.get(url, params=params, timeout=10)
                                
                                if response.status_code == 200:
                                                    return response.json()
                                else:
                                                    logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                                                    return None
                                                    
                except Exception as e:
                                logger.error(f"Error fetching Facebook insights: {str(e)}")
                                return None
                        
            def validate_credentials(self) -> bool:
                        """
                                Validate that Facebook credentials are configured and working
                                        
                                                Returns:
                                                            True if credentials are valid, False otherwise
                                                                    """
                        if not self.page_access_token or not self.page_id:
                                        logger.error("Facebook credentials missing")
                                        return False
                                    
                        try:
                                        url = f"{self.base_url}/{self.page_id}"
                                        params = {'access_token': self.page_access_token}
                                        
                                        response = requests.get(url, params=params, timeout=10)
                                        
                                        if response.status_code == 200:
                                                            page_info = response.json()
                                                            logger.info(f"Facebook credentials valid. Page: {page_info.get('name')}")
                                                            return True
                                        else:
                                                            logger.error(f"Invalid Facebook credentials. Response: {response.text}")
                                                            return False
                                                            
                        except Exception as e:
                                        logger.error(f"Error validating Facebook credentials: {str"
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
