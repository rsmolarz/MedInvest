"""Referral System Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from utils.referral_system import ReferralManager, process_referral_signup, get_user_referral_tier, REFERRAL_TIERS

referral_bp = Blueprint('referral', __name__, url_prefix='/referral')


@referral_bp.route('/')
@login_required
def dashboard():
    """Display referral dashboard."""
    manager = ReferralManager(current_user)
    stats = manager.get_stats()
    referrals = manager.get_referrals()
    tier = get_user_referral_tier(stats['successful_referrals'])
    referral_link = manager.get_referral_link(request.host_url.rstrip('/'))
    
    return render_template('referral/dashboard.html',
                         stats=stats,
                         referrals=referrals,
                         tier=tier,
                         tiers=REFERRAL_TIERS,
                         referral_code=current_user.referral_code,
                         referral_link=referral_link)


@referral_bp.route('/generate-code', methods=['POST'])
@login_required
def generate_code():
    """Generate a new referral code."""
    manager = ReferralManager(current_user)
    code = manager.generate_code()
    flash(f'Your new referral code is: {code}', 'success')
    return redirect(url_for('referral.dashboard'))


@referral_bp.route('/stats')
@login_required
def stats_api():
    """Get referral stats as JSON."""
    manager = ReferralManager(current_user)
    stats = manager.get_stats()
    return jsonify(stats)


@referral_bp.route('/ref/<code>')
def referral_landing(code):
    """Landing page for referral links."""
    from models import User
    referrer = User.query.filter_by(referral_code=code).first()
    
    if not referrer:
        flash('Invalid referral code.', 'error')
        return redirect(url_for('main.index'))
    
    from flask import session
    session['referral_code'] = code
    
    return render_template('referral/landing.html',
                         referrer=referrer,
                         code=code)
