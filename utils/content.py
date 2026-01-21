"""
Content Utilities - Parse mentions, hashtags, and format content
"""
import re
import html
from datetime import datetime
from flask import url_for
from markupsafe import Markup


# Regex patterns
MENTION_PATTERN = re.compile(r'@(\w+)')
HASHTAG_PATTERN = re.compile(r'#(\w+)')


def extract_mentions(text):
    """Extract all @mentions from text, returns list of usernames"""
    if not text:
        return []
    return MENTION_PATTERN.findall(text)


def extract_hashtags(text):
    """Extract all #hashtags from text, returns list of tag names (without #)"""
    if not text:
        return []
    return HASHTAG_PATTERN.findall(text)


def process_mentions(text, db, User, Mention, Post=None, Comment=None, author=None):
    """
    Process mentions in text:
    - Find mentioned users
    - Create Mention records
    - Return list of mentioned user IDs for notifications
    """
    from models import Mention as MentionModel
    
    usernames = extract_mentions(text)
    mentioned_user_ids = []
    
    for username in usernames:
        # Try to find user by username (first_name + last_name or email prefix)
        user = User.query.filter(
            db.or_(
                db.func.lower(db.func.concat(User.first_name, User.last_name)) == username.lower(),
                db.func.lower(User.first_name) == username.lower(),
                db.func.lower(User.email).like(f'{username.lower()}@%')
            )
        ).first()
        
        if user and author and user.id != author.id:
            mention = MentionModel(
                mentioned_user_id=user.id,
                mentioning_user_id=author.id,
                post_id=Post.id if Post else None,
                comment_id=Comment.id if Comment else None
            )
            db.session.add(mention)
            mentioned_user_ids.append(user.id)
    
    return mentioned_user_ids


def process_hashtags(text, db):
    """
    Process hashtags in text:
    - Find or create hashtag records
    - Return list of Hashtag objects
    """
    from models import Hashtag, PostHashtag
    
    tag_names = extract_hashtags(text)
    hashtags = []
    
    for name in tag_names:
        name_lower = name.lower()
        
        # Find or create hashtag
        hashtag = Hashtag.query.filter_by(name=name_lower).first()
        
        if not hashtag:
            hashtag = Hashtag(name=name_lower)
            db.session.add(hashtag)
            db.session.flush()
        
        # Update usage stats
        hashtag.post_count += 1
        hashtag.last_used_at = datetime.utcnow()
        hashtag.posts_today += 1
        hashtag.posts_this_week += 1
        
        hashtags.append(hashtag)
    
    return hashtags


def link_hashtag(post_id, hashtag, db):
    """Create association between post and hashtag"""
    from models import PostHashtag
    
    existing = PostHashtag.query.filter_by(
        post_id=post_id,
        hashtag_id=hashtag.id
    ).first()
    
    if not existing:
        link = PostHashtag(post_id=post_id, hashtag_id=hashtag.id)
        db.session.add(link)


def render_content_with_links(text):
    """
    Render text content with clickable @mentions and #hashtags
    Returns safe HTML string
    """
    if not text:
        return ''
    
    # Escape HTML tags but preserve quotes/apostrophes
    text = html.escape(text, quote=False)
    
    # Use placeholders to avoid regex conflicts with CSS color codes
    MENTION_PLACEHOLDER = '\x00MENTION_{}\x00'
    HASHTAG_PLACEHOLDER = '\x00HASHTAG_{}\x00'
    
    mentions_found = []
    hashtags_found = []
    
    # First pass: find all hashtags (must be word characters only, not hex codes)
    # Only match hashtags that start with a letter (not digits like hex codes)
    hashtag_word_pattern = re.compile(r'#([a-zA-Z]\w*)')
    
    def collect_hashtag(match):
        tag = match.group(1)
        idx = len(hashtags_found)
        hashtags_found.append(tag)
        return HASHTAG_PLACEHOLDER.format(idx)
    
    text = hashtag_word_pattern.sub(collect_hashtag, text)
    
    # Second pass: find all mentions
    def collect_mention(match):
        username = match.group(1)
        idx = len(mentions_found)
        mentions_found.append(username)
        return MENTION_PLACEHOLDER.format(idx)
    
    text = MENTION_PATTERN.sub(collect_mention, text)
    
    # Now replace placeholders with actual HTML
    for idx, username in enumerate(mentions_found):
        try:
            from models import User
            from app import db
            username_clean = username.lower().replace("'", "")
            user = User.query.filter(
                db.or_(
                    db.func.lower(db.func.replace(db.func.concat(User.first_name, User.last_name), "'", "")) == username_clean,
                    db.func.lower(db.func.replace(User.first_name, "'", "")) == username_clean
                )
            ).first()
            if user:
                link = f'<a href="/profile/{user.id}" class="mention-link" style="color: rgb(59, 130, 246); background-color: rgba(59, 130, 246, 0.15); padding: 2px 6px; border-radius: 12px; font-weight: 600; text-decoration: none;">@{username}</a>'
            else:
                link = f'<a href="/search?q={username}" class="mention-link" style="color: rgb(59, 130, 246); background-color: rgba(59, 130, 246, 0.15); padding: 2px 6px; border-radius: 12px; font-weight: 600; text-decoration: none;">@{username}</a>'
        except Exception:
            link = f'<a href="/search?q={username}" class="mention-link" style="color: rgb(59, 130, 246); background-color: rgba(59, 130, 246, 0.15); padding: 2px 6px; border-radius: 12px; font-weight: 600; text-decoration: none;">@{username}</a>'
        text = text.replace(MENTION_PLACEHOLDER.format(idx), link, 1)
    
    for idx, tag in enumerate(hashtags_found):
        link = f'<a href="/hashtag/{tag.lower()}" class="hashtag-link" style="color: rgb(139, 92, 246); font-weight: 600; text-decoration: none;">#{tag}</a>'
        text = text.replace(HASHTAG_PLACEHOLDER.format(idx), link, 1)
    
    # Convert newlines to <br>
    text = text.replace('\n', '<br>')
    
    return Markup(text)


def get_trending_hashtags(limit=10):
    """Get trending hashtags based on recent usage"""
    from models import Hashtag
    
    return Hashtag.query.filter(
        Hashtag.posts_this_week > 0
    ).order_by(
        Hashtag.posts_this_week.desc(),
        Hashtag.post_count.desc()
    ).limit(limit).all()


def search_users_for_mention(query, limit=10):
    """Search users for @mention autocomplete"""
    from models import User
    from app import db
    
    if not query:
        return []
    
    query_lower = query.lower()
    
    users = User.query.filter(
        db.or_(
            db.func.lower(User.first_name).like(f'{query_lower}%'),
            db.func.lower(User.last_name).like(f'{query_lower}%'),
            db.func.lower(User.email).like(f'{query_lower}%')
        )
    ).limit(limit).all()
    
    return [{
        'id': u.id,
        'name': u.full_name,
        'username': u.first_name.lower() + u.last_name.lower(),
        'specialty': (u.specialty or '').replace('_', ' ').title(),
        'avatar': u.first_name[0] + u.last_name[0],
        'is_verified': u.is_verified
    } for u in users]


def search_hashtags(query, limit=10):
    """Search hashtags for autocomplete"""
    from models import Hashtag
    
    if not query:
        return []
    
    query = query.lower()
    
    hashtags = Hashtag.query.filter(
        Hashtag.name.like(f'{query}%')
    ).order_by(Hashtag.post_count.desc()).limit(limit).all()
    
    return [{
        'name': h.name,
        'post_count': h.post_count
    } for h in hashtags]
