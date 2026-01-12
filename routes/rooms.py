"""
Rooms Routes - Investment discussion rooms
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from models import Room, Post, PostVote, Comment

rooms_bp = Blueprint('rooms', __name__, url_prefix='/rooms')


@rooms_bp.route('/')
@login_required
def list_rooms():
    """List all investment rooms"""
    rooms = Room.query.order_by(Room.member_count.desc()).all()
    
    # Group by category
    categories = {}
    for room in rooms:
        cat = room.category or 'Other'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(room)
    
    return render_template('rooms/list.html', categories=categories, rooms=rooms)


@rooms_bp.route('/<slug>')
@login_required
def view_room(slug):
    """View a specific room and its posts"""
    room = Room.query.filter_by(slug=slug).first_or_404()
    
    # Check premium access
    if room.is_premium_only and not current_user.is_premium:
        flash('This room is for premium members only', 'warning')
        return redirect(url_for('subscription.pricing'))
    
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'new')  # new, top, hot
    
    query = Post.query.filter_by(room_id=room.id)
    
    if sort == 'top':
        query = query.order_by((Post.upvotes - Post.downvotes).desc())
    elif sort == 'hot':
        # Simple hot algorithm: score / age
        query = query.order_by(Post.upvotes.desc(), Post.created_at.desc())
    else:
        query = query.order_by(Post.created_at.desc())
    
    posts = query.paginate(page=page, per_page=20, error_out=False)
    
    # Get user votes
    user_votes = {}
    if current_user.is_authenticated:
        post_ids = [p.id for p in posts.items]
        votes = PostVote.query.filter(
            PostVote.post_id.in_(post_ids),
            PostVote.user_id == current_user.id
        ).all()
        user_votes = {v.post_id: v.vote_type for v in votes}
    
    return render_template('rooms/detail.html', 
                         room=room, 
                         posts=posts,
                         user_votes=user_votes,
                         sort=sort)


@rooms_bp.route('/<slug>/post', methods=['POST'])
@login_required
def create_room_post(slug):
    """Create a post in a specific room"""
    room = Room.query.filter_by(slug=slug).first_or_404()
    
    if room.is_premium_only and not current_user.is_premium:
        flash('Premium membership required to post here', 'warning')
        return redirect(url_for('subscription.pricing'))
    
    content = request.form.get('content', '').strip()
    is_anonymous = request.form.get('is_anonymous') == 'on'
    
    if not content:
        flash('Post content cannot be empty', 'error')
        return redirect(url_for('rooms.view_room', slug=slug))
    
    anonymous_name = None
    if is_anonymous and current_user.specialty:
        specialty_titles = {
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
        anonymous_name = f"Anonymous {specialty_titles.get(current_user.specialty, 'Physician')}"
    elif is_anonymous:
        anonymous_name = "Anonymous Physician"
    
    post = Post(
        author_id=current_user.id,
        room_id=room.id,
        content=content,
        is_anonymous=is_anonymous,
        anonymous_name=anonymous_name
    )
    
    db.session.add(post)
    current_user.add_points(5)
    db.session.commit()
    
    flash('Post created!', 'success')
    return redirect(url_for('rooms.view_room', slug=slug))


@rooms_bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    """View a single post with comments"""
    post = Post.query.get_or_404(post_id)
    post.view_count += 1
    db.session.commit()
    
    comments = Comment.query.filter_by(post_id=post_id, parent_id=None)\
                           .order_by(Comment.created_at.asc()).all()
    
    # Get user's vote
    user_vote = None
    if current_user.is_authenticated:
        vote = PostVote.query.filter_by(post_id=post_id, user_id=current_user.id).first()
        user_vote = vote.vote_type if vote else None
    
    return render_template('rooms/post.html', 
                         post=post, 
                         comments=comments,
                         user_vote=user_vote)


@rooms_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    """Add a comment to a post"""
    post = Post.query.get_or_404(post_id)
    
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    is_anonymous = request.form.get('is_anonymous') == 'on'
    
    if not content:
        flash('Comment cannot be empty', 'error')
        return redirect(url_for('rooms.view_post', post_id=post_id))
    
    comment = Comment(
        post_id=post_id,
        author_id=current_user.id,
        parent_id=parent_id,
        content=content,
        is_anonymous=is_anonymous
    )
    
    post.comment_count += 1
    db.session.add(comment)
    current_user.add_points(2)
    db.session.commit()
    
    flash('Comment added!', 'success')
    return redirect(url_for('rooms.view_post', post_id=post_id))
