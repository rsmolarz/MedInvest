"""
Rooms Routes - Investment discussion rooms
"""
import re
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from models import Room, Post, PostVote, Comment, RoomMembership, PostMention, User, PostMedia, Bookmark, PostHashtag, Mention, Notification, Petition, PetitionSignature, UserMedicalLicense
from utils.content import extract_mentions, render_content_with_links
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
    """List all investment rooms with filtering and sorting"""
    # Filter parameters
    category_filter = request.args.get('category')
    sort_by = request.args.get('sort', 'popular')
    search = request.args.get('q', '').strip()
    
    query = Room.query
    
    if category_filter:
        query = query.filter(Room.category == category_filter)
    
    if search:
        query = query.filter(Room.name.ilike(f'%{search}%'))
    
    # Sorting
    if sort_by == 'newest':
        query = query.order_by(Room.created_at.desc())
    elif sort_by == 'alphabetical':
        query = query.order_by(Room.name.asc())
    elif sort_by == 'active':
        query = query.order_by(Room.post_count.desc())
    else:
        query = query.order_by(Room.member_count.desc())
    
    rooms = query.all()
    
    # Group by category for display
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
                         room_icons=ROOM_ICONS,
                         category_filter=category_filter,
                         sort_by=sort_by,
                         search=search)


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
    import logging
    import traceback
    try:
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
        
        # Debug: Log room and post data before rendering
        logging.debug(f"Rendering room '{slug}' with {len(posts.items)} posts, user: {current_user.id if current_user.is_authenticated else 'anon'}")
        
        # Get active petitions for this room
        active_petitions = Petition.query.filter_by(
            room_id=room.id, 
            is_active=True, 
            status='active'
        ).order_by(Petition.created_at.desc()).all()
        
        try:
            return render_template('rooms/detail.html', 
                                 room=room, 
                                 posts=posts,
                                 user_votes=user_votes,
                                 sort=sort,
                                 active_petitions=active_petitions,
                                 render_content=render_content_with_links)
        except Exception as template_error:
            logging.error(f"Template error in view_room for slug '{slug}': {template_error}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            logging.error(f"Room data: id={room.id}, name={room.name}, member_count={room.member_count}")
            logging.error(f"Current user: id={current_user.id}, first_name={current_user.first_name}, last_name={current_user.last_name}")
            raise
    except Exception as e:
        logging.error(f"Error in view_room for slug '{slug}': {e}", exc_info=True)
        raise


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
def view_post(post_id):
    """View a single post with comments - publicly accessible"""
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
        if current_user.is_authenticated and vote.user and vote.user.id != current_user.id:
            likers.append(vote.user)
    
    return render_template('rooms/post.html', 
                         post=post, 
                         comments=comments,
                         user_vote=user_vote,
                         likers=likers,
                         render_content=render_content_with_links)


@rooms_bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    """Delete a post - only owner or admin can delete"""
    post = Post.query.get_or_404(post_id)
    
    if post.author_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this post.', 'error')
        return redirect(url_for('rooms.view_post', post_id=post_id))
    
    try:
        PostMedia.query.filter_by(post_id=post_id).delete()
        PostVote.query.filter_by(post_id=post_id).delete()
        Comment.query.filter_by(post_id=post_id).delete()
        Bookmark.query.filter_by(post_id=post_id).delete()
        PostMention.query.filter_by(post_id=post_id).delete()
        PostHashtag.query.filter_by(post_id=post_id).delete()
        Mention.query.filter_by(post_id=post_id).delete()
        Notification.query.filter_by(post_id=post_id).delete()
        
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {str(e)}', 'error')
    
    return redirect(url_for('main.feed'))


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


# ============================================================================
# PETITION ROUTES
# ============================================================================

US_STATES = [
    ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
    ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
    ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
    ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
    ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
    ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
    ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
    ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
    ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
    ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
    ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
    ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'), ('WY', 'Wyoming'), ('DC', 'District of Columbia'),
    ('AS', 'American Samoa'), ('GU', 'Guam'), ('MP', 'Northern Mariana Islands'),
    ('PR', 'Puerto Rico'), ('VI', 'U.S. Virgin Islands')
]


@rooms_bp.route('/petition/<int:petition_id>')
@login_required
def view_petition(petition_id):
    """View a petition and sign form"""
    petition = Petition.query.get_or_404(petition_id)
    
    if not petition.is_active or petition.status not in ['active']:
        flash('This petition is not currently accepting signatures.', 'warning')
        if petition.room:
            return redirect(url_for('rooms.view_room', slug=petition.room.slug))
        return redirect(url_for('rooms.list_rooms'))
    
    already_signed = PetitionSignature.query.filter_by(
        petition_id=petition_id, 
        user_id=current_user.id
    ).first() is not None
    
    user_licenses = current_user.medical_licenses.all()
    
    primary_license = None
    if current_user.medical_license and current_user.license_state:
        primary_license = {
            'license_number': current_user.medical_license,
            'state': current_user.license_state
        }
    
    recent_signatures = petition.signatures.filter_by(is_public=True)\
                                          .order_by(PetitionSignature.signed_at.desc())\
                                          .limit(10).all()
    
    return render_template('rooms/petition.html',
                          petition=petition,
                          already_signed=already_signed,
                          user_licenses=user_licenses,
                          primary_license=primary_license,
                          recent_signatures=recent_signatures,
                          us_states=US_STATES)


@rooms_bp.route('/petition/<int:petition_id>/sign', methods=['POST'])
@login_required
def sign_petition(petition_id):
    """Sign a petition"""
    petition = Petition.query.get_or_404(petition_id)
    
    if not petition.is_active or petition.status != 'active':
        flash('This petition is not currently accepting signatures.', 'error')
        return redirect(url_for('rooms.view_petition', petition_id=petition_id))
    
    existing_signature = PetitionSignature.query.filter_by(
        petition_id=petition_id,
        user_id=current_user.id
    ).first()
    
    if existing_signature:
        flash('You have already signed this petition.', 'warning')
        return redirect(url_for('rooms.view_petition', petition_id=petition_id))
    
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    address_line1 = request.form.get('address_line1', '').strip()
    address_line2 = request.form.get('address_line2', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    zip_code = request.form.get('zip_code', '').strip()
    license_number = request.form.get('license_number', '').strip()
    license_state = request.form.get('license_state', '').strip()
    comments = request.form.get('comments', '').strip()
    is_public = request.form.get('is_public') == 'on'
    
    errors = []
    if not full_name:
        errors.append('Full name is required')
    if not email:
        errors.append('Email is required')
    if not address_line1:
        errors.append('Address is required')
    if not city:
        errors.append('City is required')
    if not state:
        errors.append('State is required')
    if not zip_code:
        errors.append('ZIP code is required')
    if not license_number:
        errors.append('Medical license number is required')
    if not license_state:
        errors.append('License state is required')
    
    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('rooms.view_petition', petition_id=petition_id))
    
    signature = PetitionSignature(
        petition_id=petition_id,
        user_id=current_user.id,
        full_name=full_name,
        email=email,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        state=state,
        zip_code=zip_code,
        license_number=license_number,
        license_state=license_state,
        comments=comments if comments else None,
        is_public=is_public,
        ip_address=request.remote_addr
    )
    
    db.session.add(signature)
    petition.signature_count += 1
    db.session.commit()
    
    flash('Thank you for signing this petition!', 'success')
    return redirect(url_for('rooms.view_petition', petition_id=petition_id))


@rooms_bp.route('/my-licenses')
@login_required
def my_licenses():
    """View and manage medical licenses"""
    licenses = current_user.medical_licenses.order_by(UserMedicalLicense.is_primary.desc()).all()
    return render_template('rooms/my_licenses.html', licenses=licenses, us_states=US_STATES)


@rooms_bp.route('/my-licenses/add', methods=['POST'])
@login_required
def add_license():
    """Add a new medical license"""
    license_number = request.form.get('license_number', '').strip()
    state = request.form.get('state', '').strip()
    license_type = request.form.get('license_type', 'MD').strip()
    is_primary = request.form.get('is_primary') == 'on'
    
    if not license_number or not state:
        flash('License number and state are required', 'error')
        return redirect(url_for('rooms.my_licenses'))
    
    existing = UserMedicalLicense.query.filter_by(
        user_id=current_user.id,
        license_number=license_number,
        state=state
    ).first()
    
    if existing:
        flash('This license is already on file', 'warning')
        return redirect(url_for('rooms.my_licenses'))
    
    if is_primary:
        UserMedicalLicense.query.filter_by(user_id=current_user.id, is_primary=True)\
                                .update({'is_primary': False})
    
    new_license = UserMedicalLicense(
        user_id=current_user.id,
        license_number=license_number,
        state=state,
        license_type=license_type,
        is_primary=is_primary
    )
    
    db.session.add(new_license)
    
    if is_primary:
        current_user.medical_license = license_number
        current_user.license_state = state
    
    db.session.commit()
    
    flash('Medical license added successfully!', 'success')
    return redirect(url_for('rooms.my_licenses'))


@rooms_bp.route('/my-licenses/<int:license_id>/delete', methods=['POST'])
@login_required
def delete_license(license_id):
    """Delete a medical license"""
    license = UserMedicalLicense.query.get_or_404(license_id)
    
    if license.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('rooms.my_licenses'))
    
    was_primary = license.is_primary
    
    db.session.delete(license)
    
    if was_primary:
        next_license = UserMedicalLicense.query.filter_by(user_id=current_user.id).first()
        if next_license:
            next_license.is_primary = True
            current_user.medical_license = next_license.license_number
            current_user.license_state = next_license.state
        else:
            current_user.medical_license = None
            current_user.license_state = None
    
    db.session.commit()
    
    flash('License removed', 'success')
    return redirect(url_for('rooms.my_licenses'))


@rooms_bp.route('/my-licenses/<int:license_id>/set-primary', methods=['POST'])
@login_required
def set_primary_license(license_id):
    """Set a license as primary"""
    license = UserMedicalLicense.query.get_or_404(license_id)
    
    if license.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('rooms.my_licenses'))
    
    UserMedicalLicense.query.filter_by(user_id=current_user.id, is_primary=True)\
                            .update({'is_primary': False})
    
    license.is_primary = True
    current_user.medical_license = license.license_number
    current_user.license_state = license.state
    
    db.session.commit()
    
    flash(f'License for {license.state} set as primary', 'success')
    return redirect(url_for('rooms.my_licenses'))
