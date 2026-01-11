"""
Notifications Routes - User notifications system
"""
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app import db
from models import Notification, NotificationType, User

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
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'type': n.notification_type.value,
            'title': n.title,
            'message': n.message,
            'url': n.url,
            'is_read': n.is_read,
            'actor_name': n.actor.full_name if n.actor else None,
            'actor_initial': n.actor.first_name[0] if n.actor else '?',
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

def create_notification(user_id, notification_type, title, message, 
                       actor_id=None, post_id=None, comment_id=None, 
                       ama_id=None, deal_id=None, url=None, send_push=True):
    """Create a notification for a user and optionally send push"""
    # Don't notify yourself
    if actor_id and actor_id == user_id:
        return None
    
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        actor_id=actor_id,
        post_id=post_id,
        comment_id=comment_id,
        ama_id=ama_id,
        deal_id=deal_id,
        url=url
    )
    db.session.add(notification)
    db.session.flush()  # Get ID before sending push
    
    # Send push notification
    if send_push:
        try:
            from routes.push import send_push_notification, should_send_push
            
            if should_send_push(user_id, notification_type):
                send_push_notification(
                    user_id=user_id,
                    title=title,
                    body=message,
                    url=url or '/notifications',
                    tag=f'{notification_type.value}-{notification.id}'
                )
        except Exception as e:
            # Don't fail notification creation if push fails
            print(f"Push notification error: {e}")
    
    return notification


def notify_mention(mentioned_user_id, mentioning_user, post=None, comment=None):
    """Notify a user they were mentioned"""
    if post:
        url = f'/rooms/post/{post.id}'
        message = f'{mentioning_user.full_name} mentioned you in a post'
    else:
        url = f'/rooms/post/{comment.post_id}'
        message = f'{mentioning_user.full_name} mentioned you in a comment'
    
    create_notification(
        user_id=mentioned_user_id,
        notification_type=NotificationType.MENTION,
        title='You were mentioned! 💬',
        message=message,
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
        title='Someone liked your post! ❤️',
        message=f'{liker.full_name} liked your post',
        actor_id=liker.id,
        post_id=post.id,
        url=f'/rooms/post/{post.id}'
    )


def notify_comment(post_author_id, commenter, post, comment):
    """Notify post author of a comment"""
    # Truncate comment for notification
    comment_preview = comment.content[:50] + '...' if len(comment.content) > 50 else comment.content
    
    create_notification(
        user_id=post_author_id,
        notification_type=NotificationType.COMMENT,
        title='New comment on your post! 💬',
        message=f'{commenter.full_name}: "{comment_preview}"',
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
        title='New follower! 👋',
        message=f'{follower.full_name} started following you',
        actor_id=follower.id,
        url=f'/profile/{follower.id}'
    )


def notify_reply(parent_comment_author_id, replier, post, comment):
    """Notify comment author of a reply"""
    reply_preview = comment.content[:50] + '...' if len(comment.content) > 50 else comment.content
    
    create_notification(
        user_id=parent_comment_author_id,
        notification_type=NotificationType.REPLY,
        title='Someone replied to your comment! 💬',
        message=f'{replier.full_name}: "{reply_preview}"',
        actor_id=replier.id,
        post_id=post.id,
        comment_id=comment.id,
        url=f'/rooms/post/{post.id}'
    )


def notify_ama_reminder(user_id, ama):
    """Send AMA reminder notification"""
    create_notification(
        user_id=user_id,
        notification_type=NotificationType.AMA_REMINDER,
        title=f'AMA starting soon! 🎙️',
        message=f'"{ama.title}" with {ama.expert_name} starts in 15 minutes',
        ama_id=ama.id,
        url=f'/ama/{ama.id}'
    )


def notify_deal_alert(user_id, deal):
    """Send new deal notification"""
    create_notification(
        user_id=user_id,
        notification_type=NotificationType.DEAL_ALERT,
        title='New Investment Opportunity! 💰',
        message=f'{deal.title} - Min: ${deal.minimum_investment:,}',
        deal_id=deal.id,
        url=f'/deals/{deal.id}'
    )


def notify_level_up(user_id, new_level):
    """Notify user they leveled up"""
    create_notification(
        user_id=user_id,
        notification_type=NotificationType.LEVEL_UP,
        title=f'Level Up! 🎉',
        message=f'Congratulations! You reached Level {new_level}',
        url='/dashboard'
    )
