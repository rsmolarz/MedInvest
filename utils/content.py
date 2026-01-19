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
    
    # Replace @mentions with links
    def mention_replacer(match):
        username = match.group(1)
        return f'<a href="/search?q=@{username}" class="mention-link">@{username}</a>'
    
    text = MENTION_PATTERN.sub(mention_replacer, text)
    
    # Replace #hashtags with links
    def hashtag_replacer(match):
        tag = match.group(1)
        return f'<a href="/hashtag/{tag.lower()}" class="hashtag-link">#{tag}</a>'
    
    text = HASHTAG_PATTERN.sub(hashtag_replacer, text)
    
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
    
    if not query:
        return []
    
    query = query.lower()
    
    users = User.query.filter(
        db.or_(
            db.func.lower(User.first_name).like(f'{query}%'),
            db.func.lower(User.last_name).like(f'{query}%'),
            db.func.lower(User.email).like(f'{query}%')
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
