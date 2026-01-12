"""
Main Routes - Home, Feed, Profile, Dashboard
"""
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import Post, Room, PostVote, Bookmark, PostMedia, User, Hashtag, NotificationType, PostScore, UserFeedPreference
from utils.content import (
    extract_mentions, extract_hashtags, process_hashtags, 
    link_hashtag, render_content_with_links, get_trending_hashtags,
    search_users_for_mention, search_hashtags
)
from utils.algorithm import generate_feed, get_user_interests, get_people_you_may_know
from routes.notifications import create_notification, notify_mention

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page or redirect to feed if logged in"""
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    return render_template('index.html')


@main_bp.route('/feed')
@login_required
def feed():
    """Main feed with posts from all rooms"""
    page = request.args.get('page', 1, type=int)
    
    posts = Post.query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get user's votes for these posts
    user_votes = {}
    if current_user.is_authenticated:
        post_ids = [p.id for p in posts.items]
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
    
    return render_template('feed.html', 
                         posts=posts, 
                         user_votes=user_votes,
                         trending=trending,
                         suggested_users=suggested_users,
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
    db.session.commit()
    
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
        user_id=current_user.id,
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
        
        # Process mentions (only if not anonymous)
        if not is_anonymous:
            mentioned_usernames = extract_mentions(content)
            for username in mentioned_usernames:
                # Find user by first name (simplified matching)
                mentioned_user = User.query.filter(
                    db.func.lower(User.first_name) == username.lower()
                ).first()
                
                if mentioned_user and mentioned_user.id != current_user.id:
                    # Create notification for mention
                    notify_mention(mentioned_user.id, current_user, post=post)
    
    current_user.add_points(5 if post_type == 'text' else 10)
    db.session.commit()
    
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
    
    posts = Post.query.filter_by(user_id=user.id, is_anonymous=False)\
                      .order_by(Post.created_at.desc()).limit(10).all()
    
    return render_template('profile.html', user=user, posts=posts)


@main_bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    """Update profile"""
    current_user.first_name = request.form.get('first_name', current_user.first_name)
    current_user.last_name = request.form.get('last_name', current_user.last_name)
    current_user.bio = request.form.get('bio', '')
    
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('main.profile'))


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
            User.last_name.ilike(f'{query}%')
        )
    ).limit(8).all()
    
    return jsonify([{
        'id': u.id,
        'name': u.full_name,
        'username': u.first_name.lower(),
        'specialty': (u.specialty or '').replace('_', ' ').title(),
        'avatar': u.first_name[0] + u.last_name[0],
        'is_verified': u.is_verified,
        'is_premium': u.is_premium
    } for u in users])


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


@main_bp.route('/user/<int:user_id>/follow', methods=['POST'])
@login_required
def follow_user(user_id):
    """Follow a user"""
    from models import UserFollow
    from routes.notifications import notify_follow
    
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    user = User.query.get_or_404(user_id)
    
    existing = UserFollow.query.filter_by(
        follower_id=current_user.id,
        following_id=user_id
    ).first()
    
    if existing:
        # Unfollow
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'following': False})
    else:
        # Follow
        follow = UserFollow(follower_id=current_user.id, following_id=user_id)
        db.session.add(follow)
        
        # Notify the user
        notify_follow(user_id, current_user)
        
        db.session.commit()
        return jsonify({'success': True, 'following': True})

