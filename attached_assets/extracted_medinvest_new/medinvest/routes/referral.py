"""
Referral Routes - Referral program
"""
from flask import Blueprint, render_template, url_for
from flask_login import login_required, current_user
from app import db
from models import Referral

referral_bp = Blueprint('referral', __name__, url_prefix='/referral')


@referral_bp.route('/')
@login_required
def index():
    """Referral program dashboard"""
    # Ensure user has a referral code
    if not current_user.referral_code:
        current_user.generate_referral_code()
        db.session.commit()
    
    # Get user's referrals
    referrals = Referral.query.filter_by(referrer_id=current_user.id)\
                             .order_by(Referral.created_at.desc()).all()
    
    # Calculate stats
    stats = {
        'total_referrals': len(referrals),
        'activated': sum(1 for r in referrals if r.referred_user_activated),
        'premium_conversions': sum(1 for r in referrals if r.referred_user_premium),
        'total_rewards': sum(r.reward_value or 0 for r in referrals)
    }
    
    # Generate referral link
    referral_link = url_for('auth.register', ref=current_user.referral_code, _external=True)
    
    return render_template('referral/index.html',
                         referral_code=current_user.referral_code,
                         referral_link=referral_link,
                         referrals=referrals,
                         stats=stats)
