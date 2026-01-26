"""Two-Factor Authentication Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from utils.two_factor_auth import TwoFactorManager

two_factor_bp = Blueprint('two_factor', __name__, url_prefix='/security')


@two_factor_bp.route('/2fa')
@login_required
def two_factor_settings():
    """Display 2FA settings page."""
    manager = TwoFactorManager(current_user)
    return render_template('security/two_factor.html', 
                         is_enabled=manager.is_enabled(),
                         user=current_user)


@two_factor_bp.route('/2fa/enable', methods=['GET', 'POST'])
@login_required
def enable_2fa():
    """Enable 2FA for the current user."""
    manager = TwoFactorManager(current_user)
    
    if manager.is_enabled():
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('two_factor.two_factor_settings'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if manager.verify_code(code):
            manager.enable()
            recovery_codes = manager.generate_recovery_codes()
            flash('Two-factor authentication has been enabled!', 'success')
            return render_template('security/recovery_codes.html', 
                                 codes=recovery_codes)
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    secret, qr_uri = manager.setup()
    return render_template('security/enable_2fa.html',
                         secret=secret,
                         qr_uri=qr_uri)


@two_factor_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA for the current user."""
    manager = TwoFactorManager(current_user)
    
    if not manager.is_enabled():
        flash('Two-factor authentication is not enabled.', 'info')
        return redirect(url_for('two_factor.two_factor_settings'))
    
    code = request.form.get('code', '').strip()
    
    if manager.verify_code(code):
        manager.disable()
        flash('Two-factor authentication has been disabled.', 'success')
    else:
        flash('Invalid verification code.', 'error')
    
    return redirect(url_for('two_factor.two_factor_settings'))


@two_factor_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    """Verify 2FA code during login."""
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    from models import User
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        manager = TwoFactorManager(user)
        
        if manager.verify_code(code):
            from flask_login import login_user
            login_user(user)
            session.pop('pending_2fa_user_id', None)
            flash('Login successful!', 'success')
            return redirect(url_for('main.index'))
        
        if manager.verify_recovery_code(code):
            from flask_login import login_user
            login_user(user)
            session.pop('pending_2fa_user_id', None)
            flash('Login successful! Note: You used a recovery code.', 'warning')
            return redirect(url_for('main.index'))
        
        flash('Invalid verification code.', 'error')
    
    return render_template('security/verify_2fa.html')


@two_factor_bp.route('/2fa/recovery-codes', methods=['POST'])
@login_required
def regenerate_recovery_codes():
    """Regenerate recovery codes."""
    manager = TwoFactorManager(current_user)
    
    if not manager.is_enabled():
        flash('Two-factor authentication is not enabled.', 'error')
        return redirect(url_for('two_factor.two_factor_settings'))
    
    code = request.form.get('code', '').strip()
    
    if not manager.verify_code(code):
        flash('Invalid verification code.', 'error')
        return redirect(url_for('two_factor.two_factor_settings'))
    
    recovery_codes = manager.generate_recovery_codes()
    flash('New recovery codes have been generated.', 'success')
    return render_template('security/recovery_codes.html', codes=recovery_codes)
