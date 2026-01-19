"""
Rooms Routes - Investment discussion rooms
"""
import re
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from models import Room, Post, PostVote, Comment, RoomMembership, PostMention, User
from utils.content import extract_mentions
from routes.notifications import notify_mention

rooms_bp = Blueprint('rooms', __name__, url_prefix='/rooms')

ROOM_CATEGORIES = [
    ('specialty', 'By Specialty'),
    ('career_stage', 'By Career Stage'),
    ('topic', 'Investment Topic'),
    ('other', 'Other')
]

ROOM_ICONS = [
    ('comments', 'Comments'),
    ('chart-line', 'Chart'),
    ('building', 'Building'),
    ('home', 'Real Estate'),
    ('briefcase', 'Briefcase'),
    ('coins', 'Coins'),
    ('piggy-bank', 'Savings'),
    ('landmark', 'Bank'),
    ('graduation-cap', 'Education'),
    ('stethoscope', 'Medical'),
    ('user-md', 'Doctor'),
    ('heartbeat', 'Cardiology'),
    ('brain', 'Neurology'),
    ('bone', 'Orthopedics'),
    ('eye', 'Ophthalmology'),
    ('baby', 'Pediatrics'),
]


def generate_slug(name):
    """Generate a URL-friendly slug from room name"""
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug.strip('-')


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
    
    return render_template('rooms/list.html', 
                         categories=categories, 
                         rooms=rooms,
                         room_categories=ROOM_CATEGORIES,
                         room_icons=ROOM_ICONS)


@rooms_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_room():
    """Create a new investment room"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'other')
        icon = request.form.get('icon', 'comments')
        
        if not name:
            flash('Room name is required', 'error')
            return redirect(url_for('rooms.list_rooms'))
        
        if len(name) < 3:
            flash('Room name must be at least 3 characters', 'error')
            return redirect(url_for('rooms.list_rooms'))
        
        if len(name) > 50:
            flash('Room name must be less than 50 characters', 'error')
            return redirect(url_for('rooms.list_rooms'))
        
        # Generate slug
        slug = generate_slug(name)
        
        # Check if room with same name or slug exists
        existing = Room.query.filter(
            (Room.name.ilike(name)) | (Room.slug == slug)
        ).first()
        
        if existing:
            flash('A room with this name already exists', 'error')
            return redirect(url_for('rooms.list_rooms'))
        
        # Create room
        room = Room(
            name=name,
            slug=slug,
            description=description,
            category=category,
            icon=icon,
            member_count=1
        )
        db.session.add(room)
        db.session.flush()
        
        # Add creator as room admin
        membership = RoomMembership(
            user_id=current_user.id,
            room_id=room.id,
            role='admin'
        )
        db.session.add(membership)
        current_user.add_points(20)
        db.session.commit()
        
        flash(f'Room "{name}" created successfully!', 'success')
        return redirect(url_for('rooms.view_room', slug=slug))
    
    # Redirect GET requests to the rooms list (modal-based creation)
    return redirect(url_for('rooms.list_rooms'))


@rooms_bp.route('/<slug>')
@login_required
def view_room(slug):
    """View a specific room and its posts"""
    room = Room.query.filter_by(slug=slug).first_or_404()
    
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
    db.session.flush()
    
    # Process @mentions - extract, save, and notify
    mentioned_usernames = extract_mentions(content)
    for username in mentioned_usernames:
        mentioned_user = User.query.filter(
            db.or_(
                db.func.lower(db.func.concat(User.first_name, User.last_name)) == username.lower(),
                db.func.lower(User.first_name) == username.lower()
            )
        ).first()
        if mentioned_user and mentioned_user.id != current_user.id:
            mention = PostMention(post_id=post.id, mentioned_user_id=mentioned_user.id)
            db.session.add(mention)
            if not is_anonymous:
                notify_mention(mentioned_user.id, current_user.id, post.id)
    
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
    
    # Get users who upvoted the post (vote_type=1 means upvote)
    likers = []
    upvotes = PostVote.query.filter_by(post_id=post_id, vote_type=1).all()
    for vote in upvotes:
        if vote.user and vote.user.id != current_user.id:
            likers.append(vote.user)
    
    return render_template('rooms/post.html', 
                         post=post, 
                         comments=comments,
                         user_vote=user_vote,
                         likers=likers)


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


@rooms_bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    """Edit a comment"""
    comment = Comment.query.get_or_404(comment_id)
    
    # Only the author can edit their comment
    if comment.author_id != current_user.id:
        flash('You can only edit your own comments', 'error')
        return redirect(url_for('rooms.view_post', post_id=comment.post_id))
    
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Comment cannot be empty', 'error')
        return redirect(url_for('rooms.view_post', post_id=comment.post_id))
    
    comment.content = content
    db.session.commit()
    
    flash('Comment updated!', 'success')
    return redirect(url_for('rooms.view_post', post_id=comment.post_id))
