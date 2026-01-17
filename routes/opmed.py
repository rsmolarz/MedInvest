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
from facebook_page import share_article, is_facebook_configured
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models import OpMedArticle, OpMedArticleLike, OpMedComment, OpMedEditorialFeedback, OpMedSubscriber, User
from facebook_page import share_article, is_facebook_configured

GHOST_WEBHOOK_SECRET = os.environ.get('GHOST_WEBHOOK_SECRET')
GHOST_CONTENT_API_KEY = os.environ.get('GHOST_CONTENT_API_KEY')
GHOST_API_URL = os.environ.get('GHOST_API_URL', 'https://the-medicine-and-money-show.ghost.io')


def auto_sync_ghost_articles():
    """Automatically sync articles from Ghost CMS on startup if database is empty"""
    if not GHOST_CONTENT_API_KEY:
        logging.debug("Ghost Content API key not configured, skipping auto-sync")
        return
    
    try:
        article_count = OpMedArticle.query.count()
        if article_count > 0:
            logging.debug(f"Op-MedInvest already has {article_count} articles, skipping auto-sync")
            return
        
        import requests
        
        logging.info("No articles found, auto-syncing from Ghost CMS...")
        
        api_url = f"{GHOST_API_URL}/ghost/api/content/posts/"
        params = {
            'key': GHOST_CONTENT_API_KEY,
            'limit': 'all',
            'include': 'tags',
            'formats': 'html'
        }
        
        response = requests.get(api_url, params=params, timeout=30)
        
        if response.status_code != 200:
            logging.error(f"Ghost API error during auto-sync: {response.status_code}")
            return
        
        data = response.json()
        posts = data.get('posts', [])
        
        if not posts:
            logging.info("No posts found in Ghost CMS")
            return
        
        system_user = User.query.filter_by(role='admin').first()
        if not system_user:
            system_user = User.query.first()
        
        if not system_user:
            logging.warning("No users in database, cannot import Ghost articles")
            return
        
        imported_count = 0
        for post in posts:
            try:
                ghost_id = post.get('id')
                title = post.get('title', 'Untitled')
                ghost_slug = post.get('slug', '')
                content_html = post.get('html', '')
                excerpt = post.get('excerpt') or post.get('custom_excerpt', '')
                feature_image = post.get('feature_image')
                published_at_str = post.get('published_at')
                
                existing = OpMedArticle.query.filter_by(ghost_id=ghost_id).first()
                if existing:
                    continue
                
                slug = ghost_slug or title.lower()
                slug = re.sub(r'[^\w\s-]', '', slug)
                slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
                slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"[:350]
                
                published_at = datetime.utcnow()
                if published_at_str:
                    try:
                        published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                    except:
                        pass
                
                tags = post.get('tags', [])
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
                    author_id=system_user.id,
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
                imported_count += 1
            except Exception as e:
                logging.error(f"Error importing Ghost post: {e}")
                continue
        
        if imported_count > 0:
            db.session.commit()
            logging.info(f"Auto-synced {imported_count} articles from Ghost CMS")
        
    except Exception as e:
        logging.error(f"Ghost auto-sync error: {e}")
        db.session.rollback()


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
        
        action = request.form.get('action', 'submit')
        status = 'draft' if action == 'draft' else 'submitted'
        
        article = OpMedArticle(
            author_id=current_user.id,
            title=html.escape(title),
            excerpt=sanitized_excerpt,
            content=sanitized_content,
            category=category,
            specialty_tag=current_user.specialty,
            status=status
        )
        
        if status == 'submitted':
            article.submitted_at = datetime.utcnow()
            article.calculate_reading_time()
        
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
        
        if status == 'draft':
            flash('Article saved as draft. You can continue editing from your Author Dashboard.', 'success')
        else:
            flash('Your article has been submitted for review. We will notify you once it is published!', 'success')
        return redirect(url_for('opmed.author_dashboard'))
    
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
        
        # Share to Facebook Page if configured
        if is_facebook_configured():
            share_article(article)
        
        logging.info(f"Imported Ghost post to Op-MedInvest: {title}")
        return jsonify({'status': 'created', 'article_id': article.id}), 201
        
    except Exception as e:
        logging.error(f"Ghost webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def import_ghost_post(post_data, admin_user):
    """Helper function to import a single Ghost post"""
    ghost_id = post_data.get('id')
    title = post_data.get('title', 'Untitled')
    ghost_slug = post_data.get('slug', '')
    content_html = post_data.get('html', '')
    excerpt = post_data.get('excerpt') or post_data.get('custom_excerpt', '')
    feature_image = post_data.get('feature_image')
    published_at_str = post_data.get('published_at')
    
    existing = OpMedArticle.query.filter_by(ghost_id=ghost_id).first()
    if existing:
        return {'status': 'skipped', 'title': title, 'reason': 'already exists'}
    
    slug = ghost_slug or title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"[:350]
    
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
    return {'status': 'imported', 'title': title, 'article': article}


@opmed_bp.route('/admin/import-ghost', methods=['GET', 'POST'])
@login_required
def import_from_ghost():
    """Admin endpoint to import all existing Ghost posts"""
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('opmed.index'))
    
    if request.method == 'POST':
        if not GHOST_CONTENT_API_KEY:
            flash('Ghost Content API key not configured', 'error')
            return redirect(url_for('opmed.import_from_ghost'))
        
        try:
            import requests
            
            api_url = f"{GHOST_API_URL}/ghost/api/content/posts/"
            params = {
                'key': GHOST_CONTENT_API_KEY,
                'limit': 'all',
                'include': 'tags',
                'formats': 'html'
            }
            
            response = requests.get(api_url, params=params, timeout=30)
            
            if response.status_code != 200:
                flash(f'Ghost API error: {response.status_code}', 'error')
                return redirect(url_for('opmed.import_from_ghost'))
            
            data = response.json()
            posts = data.get('posts', [])
            
            admin_user = User.query.filter_by(is_admin=True).first()
            if not admin_user:
                admin_user = User.query.first()
            
            results = {'imported': 0, 'skipped': 0, 'errors': 0}
            
            for post in posts:
                try:
                    result = import_ghost_post(post, admin_user)
                    if result['status'] == 'imported':
                        results['imported'] += 1
                    else:
                        results['skipped'] += 1
                except Exception as e:
                    logging.error(f"Error importing post: {str(e)}")
                    results['errors'] += 1
            
            db.session.commit()
            
            flash(f"Import complete: {results['imported']} imported, {results['skipped']} skipped, {results['errors']} errors", 'success')
            return redirect(url_for('opmed.index'))
            
        except Exception as e:
            logging.error(f"Ghost import error: {str(e)}")
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'error')
            return redirect(url_for('opmed.import_from_ghost'))
    
    existing_count = OpMedArticle.query.filter(OpMedArticle.ghost_id.isnot(None)).count()
    
    return render_template('opmed/import_ghost.html', existing_count=existing_count)


@opmed_bp.route('/guidelines')
def guidelines():
    """Submission guidelines page"""
    return render_template('opmed/guidelines.html')


@opmed_bp.route('/author-dashboard')
@login_required
def author_dashboard():
    """Author's personal dashboard with their submissions"""
    filter_status = request.args.get('filter', 'all')
    
    query = OpMedArticle.query.filter_by(author_id=current_user.id)
    
    if filter_status != 'all':
        query = query.filter_by(status=filter_status)
    
    articles = query.order_by(OpMedArticle.updated_at.desc()).all()
    
    all_articles = OpMedArticle.query.filter_by(author_id=current_user.id).all()
    stats = {
        'total': len(all_articles),
        'drafts': len([a for a in all_articles if a.status == 'draft']),
        'submitted': len([a for a in all_articles if a.status == 'submitted']),
        'under_review': len([a for a in all_articles if a.status == 'under_review']),
        'revision_requested': len([a for a in all_articles if a.status == 'revision_requested']),
        'published': len([a for a in all_articles if a.status == 'published']),
        'pending': len([a for a in all_articles if a.status in ['submitted', 'under_review']]),
        'total_views': sum(a.view_count or 0 for a in all_articles if a.status == 'published')
    }
    
    return render_template('opmed/author_dashboard.html', 
                         articles=articles, 
                         stats=stats, 
                         filter=filter_status,
                         OpMedEditorialFeedback=OpMedEditorialFeedback)


@opmed_bp.route('/editorial-dashboard')
@login_required
def editorial_dashboard():
    """Editorial dashboard for reviewing submissions"""
    if not current_user.is_admin:
        flash('Editor access required', 'error')
        return redirect(url_for('opmed.index'))
    
    filter_status = request.args.get('filter', 'submitted')
    
    query = OpMedArticle.query
    
    if filter_status == 'submitted':
        query = query.filter_by(status='submitted')
    elif filter_status == 'under_review':
        query = query.filter_by(status='under_review')
    elif filter_status == 'revision_requested':
        query = query.filter_by(status='revision_requested')
    elif filter_status == 'published':
        query = query.filter_by(status='published')
    elif filter_status == 'featured':
        query = query.filter(OpMedArticle.is_editors_pick == True)
    
    articles = query.order_by(OpMedArticle.submitted_at.desc().nullsfirst(), OpMedArticle.created_at.desc()).all()
    
    from datetime import timedelta
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    stats = {
        'submitted': OpMedArticle.query.filter_by(status='submitted').count(),
        'under_review': OpMedArticle.query.filter_by(status='under_review').count(),
        'published_this_month': OpMedArticle.query.filter(
            OpMedArticle.status == 'published',
            OpMedArticle.published_at >= month_ago
        ).count(),
        'total_published': OpMedArticle.query.filter_by(status='published').count()
    }
    
    return render_template('opmed/editorial_dashboard.html',
                         articles=articles,
                         stats=stats,
                         filter=filter_status)


@opmed_bp.route('/review/<int:article_id>')
@login_required
def review_article(article_id):
    """View article for editorial review"""
    if not current_user.is_admin:
        flash('Editor access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    
    if article.status == 'submitted':
        article.status = 'under_review'
        article.reviewed_by_id = current_user.id
        db.session.commit()
    
    return render_template('opmed/review_article.html', article=article)


@opmed_bp.route('/approve/<int:article_id>', methods=['POST'])
@login_required
def approve_article(article_id):
    """Approve and publish an article"""
    if not current_user.is_admin:
        flash('Editor access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    
    article.status = 'published'
    article.published_at = datetime.utcnow()
    article.reviewed_by_id = current_user.id
    article.reviewed_at = datetime.utcnow()
    
    if request.form.get('editors_pick'):
        article.is_editors_pick = True
    
    notes = request.form.get('notes')
    if notes:
        feedback = OpMedEditorialFeedback(
            article_id=article.id,
            editor_id=current_user.id,
            feedback_type='general',
            feedback=notes,
            decision='approve'
        )
        db.session.add(feedback)
    
    article.calculate_reading_time()
    
    db.session.commit()
    
    # Auto-post to Facebook
    if is_facebook_configured():
        fb_result = share_article(article)
        if fb_result.get('success'):
            flash(f'Article "{article.title[:30]}..." published and shared to Facebook!', 'success')
        else:
            flash(f'Article "{article.title[:30]}..." published! (Facebook post failed)', 'warning')
    else:
        flash(f'Article "{article.title[:30]}..." has been published!', 'success')
    
    return redirect(url_for('opmed.editorial_dashboard'))


@opmed_bp.route('/request-revision/<int:article_id>', methods=['POST'])
@login_required
def request_revision(article_id):
    """Request revisions from author"""
    if not current_user.is_admin:
        flash('Editor access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    
    feedback_text = request.form.get('feedback')
    if not feedback_text:
        flash('Please provide feedback for the author', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    areas = request.form.getlist('areas')
    
    article.status = 'revision_requested'
    article.revision_count = (article.revision_count or 0) + 1
    article.reviewed_by_id = current_user.id
    article.reviewed_at = datetime.utcnow()
    
    feedback = OpMedEditorialFeedback(
        article_id=article.id,
        editor_id=current_user.id,
        feedback_type='revision_request',
        feedback=feedback_text,
        is_revision_required=True,
        revision_areas=','.join(areas) if areas else None,
        decision='revise'
    )
    db.session.add(feedback)
    db.session.commit()
    
    flash(f'Revision requested for "{article.title[:30]}..."', 'success')
    return redirect(url_for('opmed.editorial_dashboard'))


@opmed_bp.route('/toggle-featured/<int:article_id>', methods=['POST'])
@login_required
def toggle_featured(article_id):
    """Toggle Editor's Pick status"""
    if not current_user.is_admin:
        flash('Editor access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    article.is_editors_pick = not article.is_editors_pick
    db.session.commit()
    
    status = "marked as Editor's Pick" if article.is_editors_pick else "removed from Editor's Picks"
    flash(f'Article {status}', 'success')
    return redirect(url_for('opmed.editorial_dashboard', filter='published'))


@opmed_bp.route('/edit/<int:article_id>', methods=['GET', 'POST'])
@login_required
def edit_article(article_id):
    """Edit an article (for drafts and revision requests)"""
    article = OpMedArticle.query.get_or_404(article_id)
    
    if article.author_id != current_user.id and not current_user.is_admin:
        flash('You can only edit your own articles', 'error')
        return redirect(url_for('opmed.author_dashboard'))
    
    if article.status not in ['draft', 'revision_requested']:
        flash('This article cannot be edited', 'error')
        return redirect(url_for('opmed.author_dashboard'))
    
    if request.method == 'POST':
        article.title = request.form.get('title', article.title)
        article.excerpt = request.form.get('excerpt', article.excerpt)
        article.content = request.form.get('content', article.content)
        article.category = request.form.get('category', article.category)
        article.specialty_tag = current_user.specialty
        article.updated_at = datetime.utcnow()
        
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename and allowed_image_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{secrets.token_hex(8)}_{filename}"
                upload_dir = os.path.join('media', 'uploads', 'opmed')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, unique_filename))
                article.cover_image_url = f'/{upload_dir}/{unique_filename}'
        
        action = request.form.get('action', 'save')
        if action == 'submit':
            article.status = 'submitted'
            article.submitted_at = datetime.utcnow()
            article.calculate_reading_time()
            flash('Article submitted for review!', 'success')
        else:
            flash('Article saved as draft', 'success')
        
        db.session.commit()
        return redirect(url_for('opmed.author_dashboard'))
    
    feedback = article.editorial_feedback.order_by(OpMedEditorialFeedback.created_at.desc()).all()
    
    return render_template('opmed/edit_article.html', 
                         article=article, 
                         categories=CATEGORIES,
                         feedback=feedback)


@opmed_bp.route('/share-facebook/<int:article_id>', methods=['POST'])
@login_required
def share_article_facebook(article_id):
    """Manually share an article to Facebook (admin only)"""
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    
    if article.status != 'published':
        flash('Only published articles can be shared', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    if not is_facebook_configured():
        flash('Facebook integration not configured', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    fb_result = share_article(article)
    if fb_result.get('success'):
        flash('Article shared to Facebook successfully!', 'success')
    else:
        flash(f'Facebook post failed: {fb_result.get("error", "unknown")}', 'error')
    
    return redirect(url_for('opmed.editorial_dashboard'))


@opmed_bp.route('/reassign-author/<int:article_id>', methods=['POST'])
@login_required
def reassign_author(article_id):
    """Reassign article author (admin only)"""
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('opmed.index'))
    
    article = OpMedArticle.query.get_or_404(article_id)
    
    new_author_email = request.form.get('author_email')
    if not new_author_email:
        flash('Please provide an author email', 'error')
        return redirect(url_for('opmed.review_article', article_id=article_id))
    
    new_author = User.query.filter_by(email=new_author_email).first()
    if not new_author:
        flash(f'No user found with email: {new_author_email}', 'error')
        return redirect(url_for('opmed.review_article', article_id=article_id))
    
    old_author = article.author
    article.author_id = new_author.id
    db.session.commit()
    
    flash(f'Article author changed from {old_author.first_name} {old_author.last_name} to {new_author.first_name} {new_author.last_name}', 'success')
    return redirect(url_for('opmed.editorial_dashboard', filter='published'))


@opmed_bp.route('/bulk-reassign-author', methods=['POST'])
@login_required
def bulk_reassign_author():
    """Bulk reassign all articles from one author to another (admin only)"""
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('opmed.index'))
    
    from_email = request.form.get('from_email')
    to_email = request.form.get('to_email')
    
    if not from_email or not to_email:
        flash('Please provide both source and target author emails', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    from_user = User.query.filter_by(email=from_email).first()
    to_user = User.query.filter_by(email=to_email).first()
    
    if not from_user:
        flash(f'No user found with email: {from_email}', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    if not to_user:
        flash(f'No user found with email: {to_email}', 'error')
        return redirect(url_for('opmed.editorial_dashboard'))
    
    articles = OpMedArticle.query.filter_by(author_id=from_user.id).all()
    count = len(articles)
    
    for article in articles:
        article.author_id = to_user.id
    
    db.session.commit()
    
    flash(f'Reassigned {count} articles from {from_user.first_name} {from_user.last_name} to {to_user.first_name} {to_user.last_name}', 'success')
    return redirect(url_for('opmed.editorial_dashboard', filter='published'))
