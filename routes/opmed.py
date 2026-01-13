"""
Op-MedInvest Routes - Essays from the Medical Investing Community
"""
import os
import re
import secrets
import html
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models import OpMedArticle, OpMedArticleLike, OpMedComment, User


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
