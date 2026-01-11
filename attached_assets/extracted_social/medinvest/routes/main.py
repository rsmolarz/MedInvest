"""
Main Routes - Home, Feed, Profile, Dashboard
"""
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import Post, Room, PostVote, Bookmark, PostMedia

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
    
    # Trending topics (simplified)
    trending = ['BackdoorRoth', 'RealEstate', 'IndexFunds', 'PSLF', 'FIRE']
    
    return render_template('feed.html', 
                         posts=posts, 
                         user_votes=user_votes,
                         trending=trending)


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
    post = Post.query.get_or_404(post_id)
    vote_type = request.form.get('vote_type', type=int)  # 1 or -1
    
    if vote_type not in [1, -1]:
        flash('Invalid vote', 'error')
        return redirect(request.referrer or url_for('main.feed'))
    
    existing_vote = PostVote.query.filter_by(
        post_id=post_id, 
        user_id=current_user.id
    ).first()
    
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
            else:
                post.downvotes += 1
                post.upvotes -= 1
            existing_vote.vote_type = vote_type
    else:
        # New vote
        vote = PostVote(post_id=post_id, user_id=current_user.id, vote_type=vote_type)
        if vote_type == 1:
            post.upvotes += 1
        else:
            post.downvotes += 1
        db.session.add(vote)
    
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
    from models import Referral
    
    referral_count = Referral.query.filter_by(referrer_id=current_user.id).count()
    
    return render_template('dashboard.html', referral_count=referral_count)


@main_bp.route('/bookmarks')
@login_required
def bookmarks():
    """User's bookmarked posts"""
    bookmarked = Bookmark.query.filter_by(user_id=current_user.id)\
                               .order_by(Bookmark.created_at.desc()).all()
    posts = [b.post for b in bookmarked]
    return render_template('bookmarks.html', posts=posts)
