"""
Main Routes - Home, Feed, Profile, Dashboard
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json
import hmac
import hashlib
import base64
import os
from app import db
from models import Post, Room, PostVote, Bookmark, Referral, User, AdCampaign, AdCreative, AdImpression, AdClick

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
    """Create a new post"""
    content = request.form.get('content', '').strip()
    room_id = request.form.get('room_id', type=int)
    is_anonymous = request.form.get('is_anonymous') == 'on'
    
    if not content:
        flash('Post content cannot be empty', 'error')
        return redirect(request.referrer or url_for('main.feed'))
    
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
        author_id=current_user.id,
        room_id=room_id,
        content=content,
        is_anonymous=is_anonymous,
        anonymous_name=anonymous_name
    )
    
    db.session.add(post)
    current_user.add_points(5)  # Points for posting
    db.session.commit()
    
    flash('Post created!', 'success')
    return redirect(request.referrer or url_for('main.feed'))


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
    if user_id:
        user = User.query.get_or_404(user_id)
    else:
        user = current_user
    
    posts = Post.query.filter_by(author_id=user.id, is_anonymous=False)\
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


# ============================================================================
# ADS SERVING SYSTEM
# ============================================================================

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _sign_ad_token(payload_b64: str) -> str:
    secret = os.environ.get('SESSION_SECRET')
    if not secret:
        raise RuntimeError("SESSION_SECRET environment variable must be set")
    mac = hmac.new(secret.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256)
    return _b64url_encode(mac.digest())


def _make_click_token(creative_id: int, user_id: int) -> str:
    payload = {
        "creative_id": creative_id,
        "user_id": user_id,
        "ts": int(datetime.utcnow().timestamp()),
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign_ad_token(payload_b64)
    return f"{payload_b64}.{sig}"


def _parse_click_token(token: str):
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign_ad_token(payload_b64), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        return payload
    except Exception:
        return None


def _load_targeting(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _matches_targeting(targeting: dict, ctx: dict) -> bool:
    if not targeting:
        return True
    if ctx.get("user_id") in set(targeting.get("exclude_user_ids", [])):
        return False
    def _in_list(key: str) -> bool:
        allowed = targeting.get(key)
        if not allowed:
            return True
        return ctx.get(key) in set(allowed)
    if not _in_list("specialty"):
        return False
    if not _in_list("role"):
        return False
    if not _in_list("state"):
        return False
    if not _in_list("placement"):
        return False
    keywords_any = targeting.get("keywords_any")
    if keywords_any:
        hay = (ctx.get("keywords") or "").lower()
        if not any(k.lower() in hay for k in keywords_any):
            return False
    return True


@main_bp.route('/ads/serve')
@login_required
def serve_ad():
    """Serve an ad based on placement and targeting."""
    placement = request.args.get('placement', 'feed')
    keywords = request.args.get('keywords', '')
    specialty = request.args.get('specialty')
    role = request.args.get('role')
    state = request.args.get('state')
    
    now = datetime.utcnow()
    ctx = {
        "user_id": current_user.id,
        "placement": placement,
        "keywords": keywords,
        "specialty": specialty or getattr(current_user, 'specialty', None),
        "role": role,
        "state": state,
    }
    
    results = db.session.query(AdCreative, AdCampaign)\
        .join(AdCampaign, AdCreative.campaign_id == AdCampaign.id)\
        .filter(AdCreative.is_active == True)\
        .filter(AdCampaign.start_at <= now)\
        .filter(AdCampaign.end_at >= now)\
        .filter(AdCreative.format == placement)\
        .order_by(AdCreative.id.desc())\
        .limit(50)\
        .all()
    
    chosen = None
    for creative, campaign in results:
        targeting = _load_targeting(campaign.targeting_json)
        if _matches_targeting(targeting, ctx):
            chosen = creative
            break
    
    if not chosen:
        return jsonify({"creative": None})
    
    token = _make_click_token(chosen.id, current_user.id)
    return jsonify({
        "creative": {
            "id": chosen.id,
            "format": chosen.format,
            "headline": chosen.headline,
            "body": chosen.body,
            "image_url": chosen.image_url,
            "cta_text": chosen.cta_text,
            "disclaimer_text": chosen.disclaimer_text,
            "click_url": f"/ads/click/{token}",
        }
    })


@main_bp.route('/ads/impression', methods=['POST'])
@login_required
def log_ad_impression():
    """Log an ad impression."""
    data = request.get_json() or {}
    creative_id = data.get('creative_id')
    placement = data.get('placement', 'feed')
    page_view_id = data.get('page_view_id')
    
    if not creative_id:
        return jsonify({"error": "creative_id required"}), 400
    
    if page_view_id:
        existing = AdImpression.query.filter_by(
            user_id=current_user.id,
            creative_id=creative_id,
            page_view_id=page_view_id
        ).first()
        if existing:
            return jsonify({"status": "ok"})
    
    impression = AdImpression(
        creative_id=creative_id,
        user_id=current_user.id,
        placement=placement,
        page_view_id=page_view_id,
        created_at=datetime.utcnow()
    )
    db.session.add(impression)
    db.session.commit()
    return jsonify({"status": "ok"})


@main_bp.route('/ads/click/<token>')
@login_required
def ad_click_redirect(token):
    """Handle ad click and redirect to landing URL."""
    payload = _parse_click_token(token)
    if not payload:
        return jsonify({"error": "Invalid click token"}), 400
    
    if payload.get("user_id") != current_user.id:
        return jsonify({"error": "Invalid user"}), 403
    
    creative_id = int(payload.get("creative_id"))
    creative = AdCreative.query.get(creative_id)
    if not creative:
        return jsonify({"error": "Creative not found"}), 404
    
    click = AdClick(
        creative_id=creative_id,
        user_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.session.add(click)
    db.session.commit()
    
    return redirect(creative.landing_url)


@main_bp.route('/health')
def health_check():
    """Fast health check endpoint for deployment"""
    return {'status': 'healthy', 'app': 'medinvest'}, 200
