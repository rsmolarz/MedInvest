"""
Book Landing Page Routes - Freedom for Doctors book → MedInvest funnel
"""
import os
import logging
import secrets
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, current_user
from datetime import datetime
from app import db
from models import User, Referral

book_bp = Blueprint('book', __name__, url_prefix='/book')


def add_book_reader_to_ghl(user):
    """Add user to GoHighLevel with 'book-reader' tag"""
    try:
        from gohighlevel import add_contact_to_ghl
        add_contact_to_ghl(user)
        logging.info(f"Added book reader to GHL: {user.email}")
    except ImportError:
        logging.warning("GoHighLevel integration not configured")
    except Exception as e:
        logging.error(f"Failed to add book reader to GHL: {e}")


@book_bp.route('/')
def landing():
    """Book landing page - Freedom for Doctors readers"""
    if current_user.is_authenticated:
        flash('Welcome back! Check out your exclusive book resources below.', 'success')
        return redirect(url_for('book.resources'))
    return render_template('book/landing.html')


@book_bp.route('/signup', methods=['POST'])
def signup():
    """Streamlined signup for book readers - minimal friction"""
    if current_user.is_authenticated:
        return redirect(url_for('book.resources'))
    
    try:
        email = request.form.get('email', '').strip().lower()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        password = request.form.get('password', '')
        
        if not all([email, first_name, password]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('book.landing'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('book.landing'))
        
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists. Please log in.', 'info')
            return redirect(url_for('auth.login'))
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name or '',
            specialty=request.form.get('specialty', ''),
            verification_notes='Source: Freedom for Doctors book'
        )
        user.set_password(password)
        user.generate_referral_code()
        user.points = 100
        
        db.session.add(user)
        db.session.commit()
        add_book_reader_to_ghl(user)
        login_user(user, remember=True)
        
        logging.info(f"New book reader signup: {user.email}")
        flash('Welcome to MedInvest! Your exclusive book resources are ready.', 'success')
        return redirect(url_for('book.resources'))
        
    except Exception as e:
        logging.error(f"Book signup error: {str(e)}")
        db.session.rollback()
        flash('Something went wrong. Please try again.', 'error')
        return redirect(url_for('book.landing'))


@book_bp.route('/resources')
def resources():
    """Exclusive resources for book readers"""
    return render_template('book/resources.html')


@book_bp.route('/10b-framework')
def framework():
    """10B Framework deep dive - bonus content"""
    if not current_user.is_authenticated:
        flash('Sign up to access this exclusive content.', 'info')
        return redirect(url_for('book.landing'))
    return render_template('book/framework.html')
