"""
Op-MedInvest Routes - Essays from the Medical Investing Community
"""
import os
import re
import secrets
import html
import logging
import hmac
import hashlib
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models import OpMedArticle, OpMedArticleLike, OpMedComment, User

GHOST_WEBHOOK_SECRET = os.environ.get('GHOST_WEBHOOK_SECRET')


def sanitize_html(content):
    """Sanitize HTML content to prevent XSS attacks"""
    if not content:
        return ''
    
    escaped = html.escape(content)
    
    escaped = escaped.replace('\n\n', '</p><p>')
    escaped = escaped.replace('\n', '<br>')
    
    escaped = f'<p>{escaped}</p>'
    
    return escaped

opmed_bp = Blueprint('opmed', __name__, url_prefix='/opmed')

CATEGORIES = {
    'all': 'All Articles',
    'market_insights': 'Market Insights',
    'retirement': 'Retirement Planning',
    'real_estate': 'Real Estate',
    'tax_strategy': 'Tax Strategy',
    'from_editors': 'From the Editors',
    'general': 'General'
}

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@opmed_bp.route('/')
def index():
    """Op-MedInvest landing page"""
    category = request.args.get('category', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = OpMedArticle.query.filter_by(status='published')
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    articles = query.order_by(OpMedArticle.published_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    featured = OpMedArticle.query.filter_by(
        status='published', is_featured=True
    ).order_by(OpMedArticle.published_at.desc()).limit(3).all()
    
    return render_template('opmed/index.html', 
                          articles=articles, 
                          featured=featured,
                          categories=CATEGORIES,
                          current_category=category)


@opmed_bp.route('/article/<slug>')
def view_article(slug):
    """View a single article"""
    article = OpMedArticle.query.filter_by(slug=slug, status='published').first_or_404()
    
    article.view_count += 1
    db.session.commit()
    
    user_liked = False
    if current_user.is_authenticated:
        user_liked = OpMedArticleLike.query.filter_by(
            article_id=article.id, user_id=current_user.id
        ).first() is not None
    
    comments = OpMedComment.query.filter_by(article_id=article.id)\
        .order_by(OpMedComment.created_at.desc()).all()
    
    related = OpMedArticle.query.filter(
        OpMedArticle.id != article.id,
        OpMedArticle.status == 'published',
        OpMedArticle.category == article.category
    ).order_by(OpMedArticle.published_at.desc()).limit(3).all()
    
    return render_template('opmed/article.html', 
                          article=article, 
                          user_liked=user_liked,
                          comments=comments,
                          related=related)


@opmed_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    """Submit a new article"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', 'general')
        
        if not title or len(title) < 10:
            flash('Title must be at least 10 characters', 'error')
            return render_template('opmed/submit.html', categories=CATEGORIES)
        
        if not content or len(content) < 500:
            flash('Article content must be at least 500 characters', 'error')
            return render_template('opmed/submit.html', categories=CATEGORIES)
        
        sanitized_content = sanitize_html(content)
        sanitized_excerpt = html.escape(excerpt[:500]) if excerpt else html.escape(content[:300]) + '...'
        
        article = OpMedArticle(
            author_id=current_user.id,
            title=html.escape(title),
            excerpt=sanitized_excerpt,
            content=sanitized_content,
            category=category,
            specialty_tag=current_user.specialty,
            status='pending_review'
        )
        article.slug = article.generate_slug()
        
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename and allowed_image_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"opmed_{secrets.token_hex(8)}.{ext}"
                
                upload_dir = os.path.join('media', 'uploads', 'opmed')
                os.makedirs(upload_dir, exist_ok=True)
                
                filepath = os.path.join(upload_dir, unique_filename)
                file.save(filepath)
                article.cover_image_url = f"/media/uploads/opmed/{unique_filename}"
        
        db.session.add(article)
        db.session.commit()
        
        flash('Your article has been submitted for review. We will notify you once it is published!', 'success')
        return redirect(url_for('opmed.my_articles'))
    
    return render_template('opmed/submit.html', categories=CATEGORIES)


@opmed_bp.route('/my-articles')
@login_required
def my_articles():
    """View user's submitted articles"""
    articles = OpMedArticle.query.filter_by(author_id=current_user.id)\
        .order_by(OpMedArticle.created_at.desc()).all()
    
    return render_template('opmed/my_articles.html', articles=articles)


@opmed_bp.route('/article/<int:article_id>/like', methods=['POST'])
@login_required
def like_article(article_id):
    """Like/unlike an article"""
    article = OpMedArticle.query.get_or_404(article_id)
    
    existing = OpMedArticleLike.query.filter_by(
        article_id=article_id, user_id=current_user.id
    ).first()
    
    if existing:
        db.session.delete(existing)
        article.like_count = max(0, article.like_count - 1)
    else:
        like = OpMedArticleLike(article_id=article_id, user_id=current_user.id)
        db.session.add(like)
        article.like_count += 1
    
    db.session.commit()
    return redirect(request.referrer or url_for('opmed.view_article', slug=article.slug))


@opmed_bp.route('/article/<int:article_id>/comment', methods=['POST'])
@login_required
def add_comment(article_id):
    """Add a comment to an article"""
    article = OpMedArticle.query.get_or_404(article_id)
    content = request.form.get('content', '').strip()
    
    if not content or len(content) < 10:
        flash('Comment must be at least 10 characters', 'error')
        return redirect(url_for('opmed.view_article', slug=article.slug))
    
    comment = OpMedComment(
        article_id=article_id,
        author_id=current_user.id,
        content=content
    )
    db.session.add(comment)
    article.comment_count += 1
    db.session.commit()
    
    flash('Comment added!', 'success')
    return redirect(url_for('opmed.view_article', slug=article.slug))


@opmed_bp.route('/why-publish')
def why_publish():
    """Why publish on Op-MedInvest page"""
    popular = OpMedArticle.query.filter_by(status='published')\
        .order_by(OpMedArticle.view_count.desc()).limit(6).all()
    
    return render_template('opmed/why_publish.html', popular_articles=popular)


@opmed_bp.route('/webhook/ghost', methods=['POST'])
def ghost_webhook():
    """
    Webhook endpoint for Ghost CMS.
    Automatically imports published posts from Ghost to Op-MedInvest.
    Configure in Ghost: Settings → Integrations → Add webhook → post.published
    """
    if not GHOST_WEBHOOK_SECRET:
        logging.warning("Ghost webhook received but GHOST_WEBHOOK_SECRET not configured")
        return jsonify({'error': 'Webhook not configured'}), 500
    
    provided_secret = request.headers.get('X-Ghost-Signature', '')
    if provided_secret:
        signature_parts = provided_secret.split(', ')
        sig_dict = {}
        for part in signature_parts:
            if '=' in part:
                key, val = part.split('=', 1)
                sig_dict[key] = val
        
        if 'sha256' in sig_dict:
            body = request.get_data()
            expected = hmac.new(
                GHOST_WEBHOOK_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(sig_dict['sha256'], expected):
                logging.warning("Ghost webhook signature mismatch")
                return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        data = request.get_json()
        
        if not data or 'post' not in data:
            return jsonify({'error': 'Invalid payload'}), 400
        
        post_data = data['post'].get('current', {})
        
        if not post_data:
            return jsonify({'error': 'No post data'}), 400
        
        ghost_id = post_data.get('id')
        title = post_data.get('title', 'Untitled')
        ghost_slug = post_data.get('slug', '')
        content_html = post_data.get('html', '')
        excerpt = post_data.get('excerpt') or post_data.get('custom_excerpt', '')
        feature_image = post_data.get('feature_image')
        published_at_str = post_data.get('published_at')
        
        existing = OpMedArticle.query.filter_by(ghost_id=ghost_id).first()
        if existing:
            existing.title = title
            existing.content = content_html
            existing.excerpt = excerpt[:500] if excerpt else None
            existing.cover_image_url = feature_image
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            logging.info(f"Updated Op-MedInvest article from Ghost: {title}")
            return jsonify({'status': 'updated', 'article_id': existing.id}), 200
        
        admin_user = User.query.filter_by(is_admin=True).first()
        if not admin_user:
            admin_user = User.query.first()
        
        if not admin_user:
            logging.error("No users in database to assign Ghost article to")
            return jsonify({'error': 'No author available'}), 500
        
        slug = ghost_slug or title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
        slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"[:350]
        
        published_at = datetime.utcnow()
        if published_at_str:
            try:
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            except:
                pass
        
        tags = post_data.get('tags', [])
        category = 'general'
        category_map = {
            'market': 'market_insights',
            'retirement': 'retirement',
            'real-estate': 'real_estate',
            'tax': 'tax_strategy',
            'editor': 'from_editors'
        }
        for tag in tags:
            tag_slug = tag.get('slug', '').lower()
            for key, cat in category_map.items():
                if key in tag_slug:
                    category = cat
                    break
        
        article = OpMedArticle(
            author_id=admin_user.id,
            title=title,
            slug=slug,
            excerpt=excerpt[:500] if excerpt else None,
            content=content_html,
            cover_image_url=feature_image,
            ghost_id=ghost_id,
            category=category,
            status='published',
            published_at=published_at
        )
        
        db.session.add(article)
        db.session.commit()
        
        logging.info(f"Imported Ghost post to Op-MedInvest: {title}")
        return jsonify({'status': 'created', 'article_id': article.id}), 201
        
    except Exception as e:
        logging.error(f"Ghost webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
