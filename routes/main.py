"""
Main Routes - Home, Feed, Profile, Dashboard
"""
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_from_directory
from flask_login import login_required, current_user
from app import db
from models import Post, Room, PostVote, Bookmark, PostMedia, User, Hashtag, NotificationType, PostScore, UserFeedPreference, InvestmentSkill, SkillEndorsement, Recommendation, PostMention
from utils.content import (
    extract_mentions, extract_hashtags, process_hashtags, 
    link_hashtag, render_content_with_links, get_trending_hashtags,
    search_users_for_mention, search_hashtags
)
from utils.algorithm import generate_feed, get_user_interests, get_people_you_may_know
from utils.news_aggregator import get_medical_investment_news, get_bloomberg_headlines
from routes.notifications import create_notification, notify_mention
from facebook_page import share_platform_post, is_facebook_configured

main_bp = Blueprint('main', __name__)

import logging


@main_bp.route('/health')
def health():
    """Fast health check endpoint for deployment - no database operations"""
    return 'OK', 200


@main_bp.route('/')
def index():
    """Landing page or redirect to feed if logged in"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    return render_template('index.html')


@main_bp.route('/privacy')
def privacy():
    """Privacy policy page"""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Terms of service page"""
    return render_template('terms.html')


@main_bp.route('/media/uploads/<path:filename>')
def serve_media(filename):
    """Serve uploaded media files (images, videos) from Object Storage or local filesystem"""
    from object_storage_utils import download_file, OBJECT_STORAGE_AVAILABLE
    from flask import make_response
    
    object_path = f"uploads/{filename}"
    
    if OBJECT_STORAGE_AVAILABLE:
        file_data = download_file(object_path)
        if file_data:
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            content_types = {
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
                'mp4': 'video/mp4', 'mov': 'video/quicktime', 'webm': 'video/webm',
                'pdf': 'application/pdf'
            }
            content_type = content_types.get(ext, 'application/octet-stream')
            response = make_response(file_data)
            response.headers['Content-Type'] = content_type
            response.headers['Cache-Control'] = 'public, max-age=31536000'
            return response
    
    media_dir = os.path.join(os.getcwd(), 'media', 'uploads')
    return send_from_directory(media_dir, filename)


@main_bp.route('/feed')
@login_required
def feed():
    """Main feed with posts - algorithmic by default, with chronological toggle"""
    try:
        return _feed_internal()
    except Exception as e:
        import traceback
        logging.error(f"Feed error: {str(e)}")
        logging.error(f"Feed traceback: {traceback.format_exc()}")
        flash(f'Feed error: {str(e)[:300]}', 'error')
        return render_template('error.html', error_code=500, error_message=f'Feed error: {str(e)[:200]}'), 500


def _feed_internal():
    """Internal feed logic - separated for error handling"""
    page = request.args.get('page', 1, type=int)
    feed_type = request.args.get('sort', 'latest')  # 'latest' or 'algorithm'
    per_page = 20
    
    if feed_type == 'latest':
        # Chronological feed (newest first)
        posts_paginated = Post.query.order_by(Post.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        post_items = posts_paginated.items
        has_next = posts_paginated.has_next
        has_prev = posts_paginated.has_prev
        total_pages = posts_paginated.pages
    else:
        # Algorithmic feed - personalized and scored
        post_items = generate_feed(current_user, db, page=page, per_page=per_page)
        # For algorithm feed, estimate pagination (simplified)
        total_posts = Post.query.count()
        total_pages = max(1, (total_posts + per_page - 1) // per_page)
        has_next = page < total_pages
        has_prev = page > 1
    
    # Get user's votes for these posts
    user_votes = {}
    if current_user.is_authenticated and post_items:
        post_ids = [p.id for p in post_items]
        votes = PostVote.query.filter(
            PostVote.post_id.in_(post_ids),
            PostVote.user_id == current_user.id
        ).all()
        user_votes = {v.post_id: v.vote_type for v in votes}
    
    # Get trending hashtags
    trending_hashtags = get_trending_hashtags(limit=8)
    
    # Fallback topics if no hashtags yet
    if not trending_hashtags:
        trending = ['BackdoorRoth', 'RealEstate', 'IndexFunds', 'PSLF', 'FIRE', 'Retirement', 'TaxStrategy', 'PassiveIncome']
    else:
        trending = [h.name for h in trending_hashtags]
    
    # Get people you may know suggestions
    suggested_users = get_people_you_may_know(current_user, limit=6)
    
    # Get aggregated news for sidebar widget from multiple sources
    try:
        articles = get_medical_investment_news(limit=5)
    except:
        articles = []
    
    # Get news articles for feed integration (interspersed with posts)
    try:
        feed_articles = get_medical_investment_news(limit=3) if page == 1 else []
    except:
        feed_articles = []
    
    # Get Bloomberg headlines for ticker
    try:
        bloomberg_headlines = get_bloomberg_headlines(limit=10) if page == 1 else []
    except:
        bloomberg_headlines = []
    
    # Create mixed feed items (posts + news)
    mixed_feed = []
    news_positions = [2, 7, 14]  # Insert news after these post positions
    news_idx = 0
    for i, post in enumerate(post_items):
        mixed_feed.append({'type': 'post', 'item': post})
        if i + 1 in news_positions and news_idx < len(feed_articles):
            mixed_feed.append({'type': 'news', 'item': feed_articles[news_idx]})
            news_idx += 1
    
    # Create a pagination-like object for template compatibility
    class FeedPagination:
        def __init__(self, items, page, has_next, has_prev, pages):
            self.items = items
            self.page = page
            self.has_next = has_next
            self.has_prev = has_prev
            self.pages = pages
            self.prev_num = page - 1 if has_prev else None
            self.next_num = page + 1 if has_next else None
    
    posts = FeedPagination(post_items, page, has_next, has_prev, total_pages)
    
    return render_template('feed.html', 
                         posts=posts, 
                         user_votes=user_votes,
                         trending=trending,
                         suggested_users=suggested_users,
                         feed_type=feed_type,
                         articles=articles,
                         mixed_feed=mixed_feed,
                         bloomberg_headlines=bloomberg_headlines,
                         render_content=render_content_with_links)


@main_bp.route('/post/create', methods=['POST'])
@login_required
def create_post():
    """Create a new post with optional media"""
    content = request.form.get('content', '').strip()
    room_id = request.form.get('room_id', type=int)
    is_anonymous = request.form.get('is_anonymous') == 'on'
    media_data = request.form.get('media_files', '[]')  # JSON string of uploaded files
    
    if not content:
        flash('Post content cannot be empty', 'error')
        return redirect(request.referrer or url_for('main.feed'))
    
    # Parse media data
    try:
        media_files = json.loads(media_data) if media_data else []
    except:
        media_files = []
    
    # Determine post type based on media
    if len(media_files) == 0:
        post_type = 'text'
    elif len(media_files) == 1:
        post_type = media_files[0].get('file_type', 'image')
    else:
        post_type = 'gallery'
    
    # Generate anonymous name if posting anonymously
    anonymous_name = None
    if is_anonymous and current_user.specialty:
        specialty_map = {
            'cardiology': 'Cardiologist',
            'anesthesiology': 'Anesthesiologist',
            'radiology': 'Radiologist',
            'surgery': 'Surgeon',
            'internal_medicine': 'Internist',
            'emergency_medicine': 'EM Physician',
            'pediatrics': 'Pediatrician',
            'psychiatry': 'Psychiatrist',
            'dermatology': 'Dermatologist',
            'orthopedics': 'Orthopedist',
            'neurology': 'Neurologist',
            'family_medicine': 'Family Physician',
        }
        anonymous_name = f"Anonymous {specialty_map.get(current_user.specialty, 'Physician')}"
    elif is_anonymous:
        anonymous_name = "Anonymous Physician"
    
    post = Post(
        user_id=current_user.id,
        room_id=room_id,
        content=content,
        post_type=post_type,
        is_anonymous=is_anonymous,
        anonymous_name=anonymous_name,
        media_count=len(media_files)
    )
    
    db.session.add(post)
    db.session.flush()  # Get post ID
    
    # Add media attachments
    for i, media in enumerate(media_files):
        post_media = PostMedia(
            post_id=post.id,
            media_type=media.get('file_type', 'image'),
            file_path=media.get('file_path', ''),
            filename=media.get('filename', ''),
            file_size=media.get('file_size', 0),
            order_index=i
        )
        db.session.add(post_media)
    
    current_user.add_points(5 if post_type == 'text' else 10)  # More points for media posts
    
    # Process @mentions - extract, save, and notify
    if content:
        mentioned_usernames = extract_mentions(content)
        for username in mentioned_usernames:
            # Match the handle format: FirstnameLastname (no spaces, no apostrophes)
            username_clean = username.lower().replace("'", "")
            mentioned_user = User.query.filter(
                db.or_(
                    db.func.lower(db.func.replace(db.func.concat(User.first_name, User.last_name), "'", "")) == username_clean,
                    db.func.lower(db.func.replace(User.first_name, "'", "")) == username_clean
                )
            ).first()
            if mentioned_user and mentioned_user.id != current_user.id:
                mention = PostMention(post_id=post.id, mentioned_user_id=mentioned_user.id)
                db.session.add(mention)
                if not is_anonymous:
                    notify_mention(mentioned_user.id, current_user.id, post.id)
    
    db.session.commit()
    
    # Share to Facebook Page if configured (non-anonymous posts only)
    logging.info(f"Post created: id={post.id}, is_anonymous={is_anonymous}")
    if not is_anonymous and is_facebook_configured():
        author_name = f"{current_user.first_name} {current_user.last_name}".strip() or "A physician"
        logging.info(f"Calling share_platform_post for post {post.id}")
        share_platform_post(post, author_name=author_name)
    else:
        logging.info(f"Skipping Facebook share: is_anonymous={is_anonymous}")
    
    flash('Post created!', 'success')
    return redirect(request.referrer or url_for('main.feed'))


@main_bp.route('/post/create/ajax', methods=['POST'])
@login_required
def create_post_ajax():
    """Create post via AJAX (for better UX with media)"""
    data = request.get_json()
    
    content = data.get('content', '').strip()
    room_id = data.get('room_id')
    is_anonymous = data.get('is_anonymous', False)
    media_files = data.get('media_files', [])
    
    if not content and not media_files:
        return jsonify({'error': 'Post must have content or media'}), 400
    
    # Determine post type
    if len(media_files) == 0:
        post_type = 'text'
    elif len(media_files) == 1:
        post_type = media_files[0].get('file_type', 'image')
    else:
        post_type = 'gallery'
    
    # Anonymous name
    anonymous_name = None
    if is_anonymous:
        if current_user.specialty:
            specialty_map = {
                'cardiology': 'Cardiologist',
                'anesthesiology': 'Anesthesiologist',
                'radiology': 'Radiologist',
                'surgery': 'Surgeon',
                'internal_medicine': 'Internist',
                'emergency_medicine': 'EM Physician',
                'pediatrics': 'Pediatrician',
                'psychiatry': 'Psychiatrist',
                'dermatology': 'Dermatologist',
                'orthopedics': 'Orthopedist',
                'neurology': 'Neurologist',
                'family_medicine': 'Family Physician',
            }
            anonymous_name = f"Anonymous {specialty_map.get(current_user.specialty, 'Physician')}"
        else:
            anonymous_name = "Anonymous Physician"
    
    post = Post(
        author_id=current_user.id,
        room_id=room_id,
        content=content or '',
        post_type=post_type,
        is_anonymous=is_anonymous,
        anonymous_name=anonymous_name,
        media_count=len(media_files)
    )
    
    db.session.add(post)
    db.session.flush()
    
    # Add media
    for i, media in enumerate(media_files):
        post_media = PostMedia(
            post_id=post.id,
            media_type=media.get('file_type', 'image'),
            file_path=media.get('file_path', ''),
            filename=media.get('filename', ''),
            file_size=media.get('file_size', 0),
            order_index=i
        )
        db.session.add(post_media)
    
    # Process hashtags
    if content:
        hashtags = process_hashtags(content, db)
        for hashtag in hashtags:
            link_hashtag(post.id, hashtag, db)
        
        # Process mentions - save records and notify
        mentioned_usernames = extract_mentions(content)
        for username in mentioned_usernames:
            # Match the handle format: FirstnameLastname (no spaces, no apostrophes)
            username_clean = username.lower().replace("'", "")
            mentioned_user = User.query.filter(
                db.or_(
                    db.func.lower(db.func.replace(db.func.concat(User.first_name, User.last_name), "'", "")) == username_clean,
                    db.func.lower(db.func.replace(User.first_name, "'", "")) == username_clean
                )
            ).first()
            if mentioned_user and mentioned_user.id != current_user.id:
                mention = PostMention(post_id=post.id, mentioned_user_id=mentioned_user.id)
                db.session.add(mention)
                if not is_anonymous:
                    notify_mention(mentioned_user.id, current_user.id, post.id)
    
    current_user.add_points(5 if post_type == 'text' else 10)
    db.session.commit()
    
    # Share to Facebook Page if configured (non-anonymous posts only)
    logging.info(f"AJAX Post created: id={post.id}, is_anonymous={is_anonymous}")
    if not is_anonymous and is_facebook_configured():
        author_name = f"{current_user.first_name} {current_user.last_name}".strip() or "A physician"
        logging.info(f"AJAX: Calling share_platform_post for post {post.id}")
        share_platform_post(post, author_name=author_name)
    else:
        logging.info(f"AJAX: Skipping Facebook share: is_anonymous={is_anonymous}")
    
    return jsonify({
        'success': True,
        'post_id': post.id,
        'message': 'Post created!'
    })


@main_bp.route('/post/<int:post_id>/vote', methods=['POST'])
@login_required
def vote_post(post_id):
    """Upvote or downvote a post"""
    from routes.notifications import notify_like
    
    post = Post.query.get_or_404(post_id)
    vote_type = request.form.get('vote_type', type=int)  # 1 or -1
    
    if vote_type not in [1, -1]:
        flash('Invalid vote', 'error')
        return redirect(request.referrer or url_for('main.feed'))
    
    existing_vote = PostVote.query.filter_by(
        post_id=post_id, 
        user_id=current_user.id
    ).first()
    
    send_notification = False
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            # Remove vote (toggle off)
            if vote_type == 1:
                post.upvotes -= 1
            else:
                post.downvotes -= 1
            db.session.delete(existing_vote)
        else:
            # Change vote
            if vote_type == 1:
                post.upvotes += 1
                post.downvotes -= 1
                send_notification = True
            else:
                post.downvotes += 1
                post.upvotes -= 1
            existing_vote.vote_type = vote_type
    else:
        # New vote
        vote = PostVote(post_id=post_id, user_id=current_user.id, vote_type=vote_type)
        if vote_type == 1:
            post.upvotes += 1
            send_notification = True
        else:
            post.downvotes += 1
        db.session.add(vote)
    
    # Notify post author of like (if not anonymous and not self)
    if send_notification and not post.is_anonymous and post.user_id != current_user.id:
        notify_like(post.user_id, current_user, post)
    
    db.session.commit()
    return redirect(request.referrer or url_for('main.feed'))


@main_bp.route('/post/<int:post_id>/bookmark', methods=['POST'])
@login_required
def bookmark_post(post_id):
    """Bookmark or unbookmark a post"""
    post = Post.query.get_or_404(post_id)
    
    existing = Bookmark.query.filter_by(
        user_id=current_user.id,
        post_id=post_id
    ).first()
    
    if existing:
        db.session.delete(existing)
        flash('Bookmark removed', 'info')
    else:
        bookmark = Bookmark(user_id=current_user.id, post_id=post_id)
        db.session.add(bookmark)
        flash('Post bookmarked!', 'success')
    
    db.session.commit()
    return redirect(request.referrer or url_for('main.feed'))


@main_bp.route('/profile')
@main_bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id=None):
    """User profile page"""
    from models import User
    
    if user_id:
        user = User.query.get_or_404(user_id)
    else:
        user = current_user
    
    is_own_profile = user.id == current_user.id
    
    if not is_own_profile and not getattr(user, 'is_profile_public', True):
        flash('This profile is private', 'info')
        return redirect(url_for('main.feed'))
    
    posts = Post.query.filter_by(author_id=user.id, is_anonymous=False)\
                      .order_by(Post.created_at.desc()).limit(10).all()
    
    skills = InvestmentSkill.query.filter_by(user_id=user.id).all()
    
    user_endorsements = {}
    for skill in skills:
        user_endorsements[skill.id] = SkillEndorsement.query.filter_by(
            skill_id=skill.id, endorser_id=current_user.id
        ).first() is not None
    
    recommendations = Recommendation.query.filter_by(
        user_id=user.id, is_visible=True
    ).order_by(Recommendation.created_at.desc()).all()
    
    return render_template('profile.html', user=user, posts=posts, 
                          skills=skills, user_endorsements=user_endorsements,
                          recommendations=recommendations, is_own_profile=is_own_profile)


@main_bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    """Update profile"""
    current_user.first_name = request.form.get('first_name', current_user.first_name)
    current_user.last_name = request.form.get('last_name', current_user.last_name)
    current_user.bio = request.form.get('bio', '')
    current_user.license_state = request.form.get('license_state', '') or None
    current_user.location = request.form.get('location', '') or None
    current_user.specialty = request.form.get('specialty', '') or None
    
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/profile/picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload profile picture"""
    import os
    import uuid
    from werkzeug.utils import secure_filename
    from flask import current_app
    
    if 'profile_picture' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('main.profile'))
    
    file = request.files['profile_picture']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.profile'))
    
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if ext not in allowed_extensions:
        flash('Invalid file type. Please use JPG, PNG, GIF, or WebP.', 'error')
        return redirect(url_for('main.profile'))
    
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 5 * 1024 * 1024:
        flash('File too large. Maximum size is 5MB.', 'error')
        return redirect(url_for('main.profile'))
    
    upload_folder = os.path.join(current_app.root_path, 'uploads', 'profiles')
    os.makedirs(upload_folder, exist_ok=True)
    
    unique_filename = f"{uuid.uuid4().hex}_{current_user.id}.{ext}"
    file_path = os.path.join(upload_folder, unique_filename)
    
    file.save(file_path)
    
    current_user.profile_image_url = f"/media/uploads/profiles/{unique_filename}"
    db.session.commit()
    
    flash('Profile picture updated!', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/profile/privacy', methods=['POST'])
@login_required
def toggle_profile_privacy():
    """Toggle profile visibility between public and private"""
    current_user.is_profile_public = not getattr(current_user, 'is_profile_public', True)
    db.session.commit()
    
    status = 'public' if current_user.is_profile_public else 'private'
    flash(f'Your profile is now {status}', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/profile/skill/add', methods=['POST'])
@login_required
def add_skill():
    """Add a new investment skill to profile"""
    name = request.form.get('skill_name', '').strip()
    category = request.form.get('skill_category', 'general')
    
    if not name:
        flash('Please enter a skill name', 'error')
        return redirect(url_for('main.profile'))
    
    existing = InvestmentSkill.query.filter_by(
        user_id=current_user.id, name=name
    ).first()
    
    if existing:
        flash('You already have this skill', 'info')
        return redirect(url_for('main.profile'))
    
    skill = InvestmentSkill(
        user_id=current_user.id,
        name=name,
        category=category
    )
    db.session.add(skill)
    db.session.commit()
    
    flash(f'Added "{name}" to your skills!', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/profile/skill/<int:skill_id>/delete', methods=['POST'])
@login_required
def delete_skill(skill_id):
    """Delete a skill from profile"""
    skill = InvestmentSkill.query.get_or_404(skill_id)
    
    if skill.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('main.profile'))
    
    db.session.delete(skill)
    db.session.commit()
    
    flash('Skill removed', 'info')
    return redirect(url_for('main.profile'))


@main_bp.route('/profile/skill/<int:skill_id>/endorse', methods=['POST'])
@login_required
def endorse_skill(skill_id):
    """Endorse a user's skill"""
    skill = InvestmentSkill.query.get_or_404(skill_id)
    
    if skill.user_id == current_user.id:
        flash("You can't endorse your own skills", 'error')
        return redirect(url_for('main.profile', user_id=skill.user_id))
    
    existing = SkillEndorsement.query.filter_by(
        skill_id=skill_id, endorser_id=current_user.id
    ).first()
    
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Endorsement removed', 'info')
    else:
        endorsement = SkillEndorsement(
            skill_id=skill_id,
            endorser_id=current_user.id
        )
        db.session.add(endorsement)
        db.session.commit()
        flash(f'You endorsed {skill.user.first_name}\'s {skill.name} skill!', 'success')
    
    return redirect(url_for('main.profile', user_id=skill.user_id))


@main_bp.route('/profile/<int:user_id>/recommend', methods=['POST'])
@login_required
def add_recommendation(user_id):
    """Write a recommendation for another user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash("You can't recommend yourself", 'error')
        return redirect(url_for('main.profile'))
    
    content = request.form.get('content', '').strip()
    relationship_type = request.form.get('relationship_type', 'colleague')
    
    if not content or len(content) < 20:
        flash('Please write at least 20 characters', 'error')
        return redirect(url_for('main.profile', user_id=user_id))
    
    existing = Recommendation.query.filter_by(
        user_id=user_id, author_id=current_user.id
    ).first()
    
    if existing:
        existing.content = content
        existing.relationship_type = relationship_type
        flash('Recommendation updated!', 'success')
    else:
        recommendation = Recommendation(
            user_id=user_id,
            author_id=current_user.id,
            content=content,
            relationship_type=relationship_type
        )
        db.session.add(recommendation)
        flash(f'Your recommendation for {user.first_name} has been added!', 'success')
    
    db.session.commit()
    return redirect(url_for('main.profile', user_id=user_id))


@main_bp.route('/recommendation/<int:rec_id>/delete', methods=['POST'])
@login_required
def delete_recommendation(rec_id):
    """Delete a recommendation (by author or recipient)"""
    rec = Recommendation.query.get_or_404(rec_id)
    
    if rec.author_id != current_user.id and rec.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('main.profile'))
    
    user_id = rec.user_id
    db.session.delete(rec)
    db.session.commit()
    
    flash('Recommendation removed', 'info')
    return redirect(url_for('main.profile', user_id=user_id))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with stats and quick actions"""
    from models import Referral, Notification
    
    referral_count = Referral.query.filter_by(referrer_id=current_user.id).count()
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).count()
    
    return render_template('dashboard.html', 
                         referral_count=referral_count,
                         unread_notifications=unread_notifications)


@main_bp.route('/bookmarks')
@login_required
def bookmarks():
    """User's bookmarked posts"""
    bookmarked = Bookmark.query.filter_by(user_id=current_user.id)\
                               .order_by(Bookmark.created_at.desc()).all()
    posts = [b.post for b in bookmarked]
    return render_template('bookmarks.html', posts=posts, render_content=render_content_with_links)


@main_bp.route('/hashtag/<tag_name>')
@login_required
def hashtag_page(tag_name):
    """View all posts with a specific hashtag"""
    from models import PostHashtag
    
    page = request.args.get('page', 1, type=int)
    tag_name = tag_name.lower()
    
    hashtag = Hashtag.query.filter_by(name=tag_name).first()
    
    if not hashtag:
        flash(f'No posts found with #{tag_name}', 'info')
        return redirect(url_for('main.feed'))
    
    # Get posts with this hashtag
    post_ids = [ph.post_id for ph in PostHashtag.query.filter_by(hashtag_id=hashtag.id).all()]
    
    posts = Post.query.filter(Post.id.in_(post_ids))\
                     .order_by(Post.created_at.desc())\
                     .paginate(page=page, per_page=20, error_out=False)
    
    # Get user votes
    user_votes = {}
    if current_user.is_authenticated:
        votes = PostVote.query.filter(
            PostVote.post_id.in_([p.id for p in posts.items]),
            PostVote.user_id == current_user.id
        ).all()
        user_votes = {v.post_id: v.vote_type for v in votes}
    
    # Related hashtags (simplified - just get other popular ones)
    related = Hashtag.query.filter(Hashtag.name != tag_name)\
                          .order_by(Hashtag.post_count.desc())\
                          .limit(5).all()
    
    return render_template('hashtag.html',
                         hashtag=hashtag,
                         posts=posts,
                         user_votes=user_votes,
                         related_hashtags=related,
                         render_content=render_content_with_links)


@main_bp.route('/search')
@login_required  
def search():
    """Search posts, users, and hashtags"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)
    
    results = {
        'posts': [],
        'users': [],
        'hashtags': []
    }
    
    if not query:
        return render_template('search.html', query='', results=results, search_type=search_type)
    
    # Search posts
    if search_type in ['all', 'posts']:
        posts = Post.query.filter(Post.content.ilike(f'%{query}%'))\
                         .order_by(Post.created_at.desc())\
                         .limit(20).all()
        results['posts'] = posts
    
    # Search users
    if search_type in ['all', 'users']:
        users = User.query.filter(
            db.or_(
                User.first_name.ilike(f'%{query}%'),
                User.last_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        ).limit(20).all()
        results['users'] = users
    
    # Search hashtags
    if search_type in ['all', 'hashtags']:
        hashtags = Hashtag.query.filter(Hashtag.name.ilike(f'%{query}%'))\
                               .order_by(Hashtag.post_count.desc())\
                               .limit(20).all()
        results['hashtags'] = hashtags
    
    return render_template('search.html', 
                         query=query, 
                         results=results, 
                         search_type=search_type,
                         render_content=render_content_with_links)


@main_bp.route('/network')
@login_required
def network():
    """Networking page - connect with colleagues"""
    try:
        from models import User, Follow, Connection
        from utils.algorithm import get_people_you_may_know
        
        tab = request.args.get('tab', 'suggestions')
        
        # Get connected user IDs from Connection table (accepted connections)
        connected_ids = set()
        accepted_connections = Connection.query.filter(
            db.or_(Connection.requester_id == current_user.id, Connection.addressee_id == current_user.id),
            Connection.status == 'accepted'
        ).all()
        for conn in accepted_connections:
            if conn.requester_id == current_user.id:
                connected_ids.add(conn.addressee_id)
            else:
                connected_ids.add(conn.requester_id)
        
        # Also include Follow-based connections for backwards compatibility
        following_ids = [f.following_id for f in 
                         Follow.query.filter_by(follower_id=current_user.id).all()]
        all_connected_ids = connected_ids.union(set(following_ids))
        
        # Pending connection requests (people who want to connect with current user)
        pending_connections = Connection.query.filter_by(
            addressee_id=current_user.id,
            status='pending'
        ).order_by(Connection.created_at.desc()).limit(50).all()
        pending_users = [User.query.get(c.requester_id) for c in pending_connections]
        pending_users = [u for u in pending_users if u]
        pending_connection_ids = {c.requester_id: c.id for c in pending_connections}
        
        # Outgoing connection requests (requests current user sent that are pending)
        outgoing_connections = Connection.query.filter_by(
            requester_id=current_user.id,
            status='pending'
        ).order_by(Connection.created_at.desc()).limit(50).all()
        outgoing_users = [User.query.get(c.addressee_id) for c in outgoing_connections]
        outgoing_users = [u for u in outgoing_users if u]
        outgoing_connection_ids = {c.addressee_id: c.id for c in outgoing_connections}
        
        suggestions = get_people_you_may_know(current_user, limit=20)
        
        # Get ALL connections involving current user (for exclusion)
        all_connection_user_ids = set()
        all_connections = Connection.query.filter(
            db.or_(Connection.requester_id == current_user.id, Connection.addressee_id == current_user.id)
        ).all()
        for conn in all_connections:
            all_connection_user_ids.add(conn.requester_id)
            all_connection_user_ids.add(conn.addressee_id)
        all_connection_user_ids.discard(current_user.id)
        
        # Combine connected IDs with all connection IDs for exclusion
        exclude_ids = all_connected_ids.union(all_connection_user_ids)
        
        # People near me
        near_me = []
        if current_user.license_state:
            near_me_query = User.query.filter(
                User.license_state == current_user.license_state,
                User.id != current_user.id
            )
            if exclude_ids:
                near_me_query = near_me_query.filter(User.id.notin_(list(exclude_ids)))
            near_me = near_me_query.order_by(User.points.desc()).limit(20).all()
        
        # People in the same specialty
        same_specialty = []
        if current_user.specialty:
            same_specialty_query = User.query.filter(
                User.specialty == current_user.specialty,
                User.id != current_user.id
            )
            if exclude_ids:
                same_specialty_query = same_specialty_query.filter(User.id.notin_(list(exclude_ids)))
            same_specialty = same_specialty_query.order_by(User.points.desc()).limit(20).all()
        
        # Colleagues = all accepted connections
        colleagues = []
        if all_connected_ids:
            colleagues = User.query.filter(
                User.id.in_(list(all_connected_ids))
            ).order_by(User.last_name).all()
        
        # New members (joined in last 7 days)
        # Exclude users we've already connected or sent connection requests to
        new_members = []
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            new_members_query = User.query.filter(
                User.created_at >= week_ago,
                User.id != current_user.id
            )
            if exclude_ids:
                new_members_query = new_members_query.filter(User.id.notin_(list(exclude_ids)))
            new_members = new_members_query.order_by(User.created_at.desc()).limit(10).all()
        except Exception:
            new_members = []
        
        return render_template('network.html',
                              tab=tab,
                              pending_users=pending_users,
                              pending_connection_ids=pending_connection_ids,
                              outgoing_users=outgoing_users,
                              outgoing_connection_ids=outgoing_connection_ids,
                              suggestions=suggestions,
                              near_me=near_me,
                              same_specialty=same_specialty,
                              colleagues=colleagues,
                              new_members=new_members,
                              pending_count=len(pending_users),
                              outgoing_count=len(outgoing_users),
                              new_member_count=len(new_members),
                              colleague_count=len(colleagues))
    except Exception as e:
        import logging
        logging.error(f"Network page error: {str(e)}")
        flash('Unable to load network page. Please try again.', 'error')
        return redirect(url_for('main.feed'))


@main_bp.route('/settings')
@login_required
def settings():
    """Account settings page"""
    tab = request.args.get('tab', 'account')
    return render_template('settings.html', tab=tab)


@main_bp.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    """Update account settings"""
    setting_type = request.form.get('setting_type', '')
    
    if setting_type == 'communication':
        current_user.email_notifications = request.form.get('email_notifications') == 'on'
        current_user.weekly_digest = request.form.get('weekly_digest') == 'on'
        flash('Communication preferences updated!', 'success')
    elif setting_type == 'privacy':
        current_user.profile_visibility = request.form.get('profile_visibility', 'public')
        current_user.show_activity = request.form.get('show_activity') == 'on'
        flash('Privacy settings updated!', 'success')
    
    db.session.commit()
    return redirect(url_for('main.settings', tab=setting_type))


@main_bp.route('/settings/disconnect/<provider>', methods=['POST'])
@login_required
def disconnect_social(provider):
    """Disconnect a social account"""
    valid_providers = ['google', 'facebook', 'apple', 'github']
    
    if provider not in valid_providers:
        flash('Invalid provider', 'error')
        return redirect(url_for('main.settings', tab='account'))
    
    # Check if user has password or another connected account
    has_password = bool(current_user.password_hash)
    connected_count = sum([
        bool(current_user.google_id),
        bool(current_user.facebook_id),
        bool(current_user.apple_id),
        bool(current_user.github_id)
    ])
    
    # Must keep at least one sign-in method
    if not has_password and connected_count <= 1:
        flash('You must keep at least one sign-in method. Set a password first or connect another account.', 'error')
        return redirect(url_for('main.settings', tab='account'))
    
    # Disconnect the account
    if provider == 'google':
        current_user.google_id = None
    elif provider == 'facebook':
        current_user.facebook_id = None
    elif provider == 'apple':
        current_user.apple_id = None
    elif provider == 'github':
        current_user.github_id = None
    
    db.session.commit()
    flash(f'{provider.title()} account disconnected successfully', 'success')
    return redirect(url_for('main.settings', tab='account'))


@main_bp.route('/security')
@login_required
def security():
    """Security center page"""
    return render_template('security.html')


@main_bp.route('/security/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    from werkzeug.security import check_password_hash, generate_password_hash
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('main.security'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('main.security'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('main.security'))
    
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('main.security'))


@main_bp.route('/advertise')
def advertise():
    """Public advertise with us page"""
    return render_template('advertise.html')


@main_bp.route('/advertise/inquiry', methods=['POST'])
def advertise_inquiry():
    """Handle advertiser inquiry form submission"""
    company = request.form.get('company', '')
    email = request.form.get('email', '')
    category = request.form.get('category', '')
    message = request.form.get('message', '')
    
    import logging
    logging.info(f"New advertiser inquiry: {company} ({email}) - {category}")
    logging.info(f"Message: {message}")
    
    flash('Thank you for your interest! We will contact you within 1-2 business days.', 'success')
    return redirect(url_for('main.advertise'))


@main_bp.route('/api/users/search')
@login_required
def api_search_users():
    """API endpoint for @mention autocomplete"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 1:
        return jsonify([])
    
    users = User.query.filter(
        db.or_(
            User.first_name.ilike(f'{query}%'),
            User.last_name.ilike(f'{query}%'),
            db.func.concat(User.first_name, User.last_name).ilike(f'{query}%')
        )
    ).limit(8).all()
    
    results = []
    for u in users:
        # Create a unique mention handle: FirstnameLastname (no spaces)
        handle = f"{u.first_name}{u.last_name}".replace(' ', '').replace("'", '')
        results.append({
            'id': u.id,
            'name': u.full_name.replace("'", "\\'"),  # Escape for JS
            'username': handle,
            'specialty': (u.specialty or '').replace('_', ' ').title(),
            'avatar': u.first_name[0] + u.last_name[0] if u.last_name else u.first_name[0],
            'is_verified': u.is_verified,
            'is_premium': u.is_premium
        })
    
    return jsonify(results)


@main_bp.route('/api/hashtags/search')
@login_required
def api_search_hashtags():
    """API endpoint for #hashtag autocomplete"""
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 1:
        return jsonify([])
    
    hashtags = Hashtag.query.filter(Hashtag.name.ilike(f'{query}%'))\
                           .order_by(Hashtag.post_count.desc())\
                           .limit(8).all()
    
    return jsonify([{
        'name': h.name,
        'post_count': h.post_count
    } for h in hashtags])


@main_bp.route('/report-bug', methods=['GET', 'POST'])
@login_required
def report_bug():
    """Submit a bug/error report"""
    from models import BugReport
    
    if request.method == 'POST':
        category = request.form.get('category', 'bug')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        page_url = request.form.get('page_url', '').strip()
        
        if not title or not description:
            flash('Please provide a title and description', 'error')
            return redirect(url_for('main.report_bug'))
        
        report = BugReport(
            reporter_id=current_user.id,
            category=category,
            title=title,
            description=description,
            page_url=page_url,
            browser_info=request.user_agent.string[:200] if request.user_agent else None
        )
        db.session.add(report)
        db.session.commit()
        
        flash('Thank you! Your report has been submitted and our team will review it.', 'success')
        return redirect(url_for('main.my_bug_reports'))
    
    return render_template('report_bug.html')


@main_bp.route('/my-bug-reports')
@login_required
def my_bug_reports():
    """View user's submitted bug reports"""
    from models import BugReport
    
    reports = BugReport.query.filter_by(reporter_id=current_user.id)\
                             .order_by(BugReport.created_at.desc()).all()
    
    return render_template('my_bug_reports.html', reports=reports)


@main_bp.route('/user/<int:user_id>/follow', methods=['POST'])
@login_required
def follow_user(user_id):
    """Follow a user"""
    from models import Follow
    from routes.notifications import notify_follow
    
    if user_id == current_user.id:
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': 'Cannot follow yourself'}), 400
        flash('Cannot follow yourself', 'error')
        return redirect(request.referrer or url_for('main.network'))
    
    user = User.query.get_or_404(user_id)
    
    existing = Follow.query.filter_by(
        follower_id=current_user.id,
        following_id=user_id
    ).first()
    
    if existing:
        # Unfollow
        db.session.delete(existing)
        db.session.commit()
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': True, 'following': False})
        flash(f'Unfollowed {user.first_name}', 'info')
    else:
        # Follow
        follow = Follow(follower_id=current_user.id, following_id=user_id)
        db.session.add(follow)
        
        # Notify the user
        notify_follow(user_id, current_user)
        
        db.session.commit()
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': True, 'following': True})
        flash(f'Now connected with {user.first_name}!', 'success')
    
    return redirect(request.referrer or url_for('main.network'))

