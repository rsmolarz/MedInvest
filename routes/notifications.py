"""
Notifications Routes - User notifications system
"""
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models import Notification, NotificationType, User, NotificationPreference
from push_service import send_push_to_user

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@notifications_bp.route('/')
@login_required
def index():
    """View all notifications"""
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).count()
    
    return render_template('notifications/index.html', 
                         notifications=notifications,
                         unread_count=unread_count,
                         filter_type=filter_type)


@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    """Get unread notification count (for navbar badge)"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})


@notifications_bp.route('/recent')
@login_required
def recent():
    """Get recent notifications for dropdown"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    def get_actor_initial(actor):
        """Safely get actor's first initial"""
        if not actor:
            return '?'
        if actor.first_name:
            return actor.first_name[0].upper()
        if actor.email:
            return actor.email[0].upper()
        return '?'
    
    def get_notification_type(n):
        """Get notification type as string"""
        if hasattr(n.notification_type, 'value'):
            return n.notification_type.value
        return str(n.notification_type) if n.notification_type else 'system'
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'type': get_notification_type(n),
            'title': n.title,
            'message': n.message,
            'url': n.url,
            'is_read': n.is_read,
            'actor_name': n.actor.full_name if n.actor else None,
            'actor_initial': get_actor_initial(n.actor),
            'created_at': n.created_at.strftime('%b %d at %I:%M %p'),
            'time_ago': get_time_ago(n.created_at)
        } for n in notifications]
    })


@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })
    db.session.commit()
    
    return jsonify({'success': True})


@notifications_bp.route('/clear', methods=['POST'])
@login_required
def clear_all():
    """Delete all notifications"""
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    return jsonify({'success': True})


def get_time_ago(dt):
    """Get human-readable time ago string"""
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f'{mins}m ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}h ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days}d ago'
    else:
        return dt.strftime('%b %d')


# =============================================================================
# NOTIFICATION CREATION HELPERS
# =============================================================================

def should_send_notification(user_id, notification_type_str):
    """Check if user has enabled this notification type in preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=user_id).first()
    if not prefs:
        return True
    
    type_mapping = {
        'like': 'in_app_likes',
        'comment': 'in_app_comments',
        'follow': 'in_app_follows',
        'mention': 'in_app_mentions',
        'new_deal': 'in_app_deals',
        'deal': 'in_app_deals',
        'ama': 'in_app_amas',
        'message': 'in_app_messages',
        'reply': 'in_app_comments',
    }
    
    pref_field = type_mapping.get(notification_type_str)
    if pref_field and hasattr(prefs, pref_field):
        return getattr(prefs, pref_field, True)
    
    return True


def create_notification(user_id, notification_type, title, message, 
                       actor_id=None, post_id=None, comment_id=None, 
                       url=None, send_push=True):
    """Create a notification for a user (respects notification preferences)"""
    # Don't notify yourself
    if actor_id and actor_id == user_id:
        return None
    
    # Convert enum to string value if needed
    if hasattr(notification_type, 'value'):
        notification_type_str = notification_type.value
    else:
        notification_type_str = str(notification_type)
    
    # Check if user has this notification type enabled
    if not should_send_notification(user_id, notification_type_str):
        return None
    
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type_str,
        title=title,
        message=message,
        actor_id=actor_id,
        post_id=post_id,
        comment_id=comment_id,
        url=url
    )
    db.session.add(notification)
    
    # Send push notification in background
    if send_push:
        full_url = url or '/notifications'
        send_push_to_user(user_id, title, message, full_url)
    
    return notification


def notify_mention(mentioned_user_id, mentioning_user, post=None, comment=None):
    """Notify a user they were mentioned"""
    if post:
        url = f'/rooms/post/{post.id}'
        message = f'mentioned you in a post'
    else:
        url = f'/rooms/post/{comment.post_id}'
        message = f'mentioned you in a comment'
    
    create_notification(
        user_id=mentioned_user_id,
        notification_type=NotificationType.MENTION,
        title='New Mention',
        message=f'{mentioning_user.full_name} {message}',
        actor_id=mentioning_user.id,
        post_id=post.id if post else None,
        comment_id=comment.id if comment else None,
        url=url
    )


def notify_like(post_author_id, liker, post):
    """Notify post author of a like"""
    create_notification(
        user_id=post_author_id,
        notification_type=NotificationType.LIKE,
        title='New Like',
        message=f'{liker.full_name} liked your post',
        actor_id=liker.id,
        post_id=post.id,
        url=f'/rooms/post/{post.id}'
    )


def notify_comment(post_author_id, commenter, post, comment):
    """Notify post author of a comment"""
    create_notification(
        user_id=post_author_id,
        notification_type=NotificationType.COMMENT,
        title='New Comment',
        message=f'{commenter.full_name} commented on your post',
        actor_id=commenter.id,
        post_id=post.id,
        comment_id=comment.id,
        url=f'/rooms/post/{post.id}'
    )


def notify_follow(followed_user_id, follower):
    """Notify user of a new follower"""
    create_notification(
        user_id=followed_user_id,
        notification_type=NotificationType.FOLLOW,
        title='New Follower',
        message=f'{follower.full_name} started following you',
        actor_id=follower.id,
        url=f'/profile/{follower.id}'
    )


def notify_reply(parent_comment_author_id, replier, post, comment):
    """Notify comment author of a reply"""
    create_notification(
        user_id=parent_comment_author_id,
        notification_type=NotificationType.REPLY,
        title='New Reply',
        message=f'{replier.full_name} replied to your comment',
        actor_id=replier.id,
        post_id=post.id,
        comment_id=comment.id,
        url=f'/rooms/post/{post.id}'
    )


@notifications_bp.route('/preferences')
@login_required
def preferences():
    """View notification preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
    
    return render_template('notifications/preferences.html', prefs=prefs)


@notifications_bp.route('/preferences/update', methods=['POST'])
@login_required
def update_preferences():
    """Update notification preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
    
    # In-app notifications
    prefs.in_app_likes = request.form.get('in_app_likes') == 'on'
    prefs.in_app_comments = request.form.get('in_app_comments') == 'on'
    prefs.in_app_follows = request.form.get('in_app_follows') == 'on'
    prefs.in_app_mentions = request.form.get('in_app_mentions') == 'on'
    prefs.in_app_deals = request.form.get('in_app_deals') == 'on'
    prefs.in_app_amas = request.form.get('in_app_amas') == 'on'
    prefs.in_app_messages = request.form.get('in_app_messages') == 'on'
    
    # Email notifications
    prefs.email_digest = request.form.get('email_digest', 'weekly')
    prefs.email_deals = request.form.get('email_deals') == 'on'
    prefs.email_events = request.form.get('email_events') == 'on'
    prefs.email_newsletter = request.form.get('email_newsletter') == 'on'
    prefs.email_marketing = request.form.get('email_marketing') == 'on'
    
    # Push notifications
    prefs.push_enabled = request.form.get('push_enabled') == 'on'
    prefs.push_likes = request.form.get('push_likes') == 'on'
    prefs.push_comments = request.form.get('push_comments') == 'on'
    prefs.push_messages = request.form.get('push_messages') == 'on'
    prefs.push_deals = request.form.get('push_deals') == 'on'
    
    db.session.commit()
    flash('Notification preferences updated', 'success')
    return redirect(url_for('notifications.preferences'))


def notify_invite_accepted(inviter_id, new_user):
    """Notify user when someone accepts their invite/referral"""
    create_notification(
        user_id=inviter_id,
        notification_type=NotificationType.INVITE_ACCEPTED,
        title='Invite Accepted!',
        message=f'{new_user.full_name} joined using your invite code! You earned 100 points.',
        actor_id=new_user.id,
        url=f'/profile/{new_user.id}'
    )
