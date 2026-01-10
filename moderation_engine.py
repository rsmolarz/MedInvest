"""Auto-moderation engine using reputation and cohort norms."""
import logging
from datetime import datetime
from app import db
from models import CohortNorm, ModerationEvent, ContentReport, Post, Comment

logger = logging.getLogger(__name__)

# Default thresholds if no cohort norm exists
DEFAULT_AUTO_HIDE_THRESHOLD = 3
DEFAULT_AUTO_LOCK_THRESHOLD = 5
DEFAULT_DOWNRANK_THRESHOLD = 2


def get_cohort_norm(cohort: str = 'global'):
    """Get cohort norm thresholds, falling back to global or defaults."""
    norm = CohortNorm.query.filter_by(cohort=cohort).first()
    if not norm:
        norm = CohortNorm.query.filter_by(cohort='global').first()
    return norm


def get_threshold(norm, threshold_name: str, default: int):
    """Get threshold value from norm or use default."""
    if norm:
        return getattr(norm, threshold_name, default)
    return default


def count_open_reports(entity_type: str, entity_id: int) -> int:
    """Count open reports for an entity."""
    return ContentReport.query.filter(
        ContentReport.entity_type == entity_type,
        ContentReport.entity_id == entity_id,
        ContentReport.status == 'open'
    ).count()


def apply_moderation(entity_type: str, entity_id: int, action: str, reason: str, 
                     performed_by_id: int = None, is_automated: bool = True):
    """Apply a moderation action and log it."""
    if entity_type == 'post':
        entity = Post.query.get(entity_id)
        if entity:
            if action == 'hide':
                entity.is_hidden = True
            elif action == 'lock':
                entity.is_locked = True
            elif action == 'downrank':
                entity.is_downranked = True
            elif action == 'unhide':
                entity.is_hidden = False
            elif action == 'unlock':
                entity.is_locked = False
    
    elif entity_type == 'comment':
        entity = Comment.query.get(entity_id)
        if entity:
            if action == 'hide':
                entity.is_hidden = True
            elif action == 'unhide':
                entity.is_hidden = False
    
    # Log moderation event
    event = ModerationEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        reason=reason,
        performed_by_id=performed_by_id,
        is_automated=is_automated
    )
    db.session.add(event)
    db.session.commit()
    
    logger.info(f"Moderation applied: {action} on {entity_type}#{entity_id}, reason: {reason}")


def check_and_moderate(entity_type: str, entity_id: int, cohort: str = 'global'):
    """Check report count and apply auto-moderation if thresholds exceeded."""
    norm = get_cohort_norm(cohort)
    
    report_count = count_open_reports(entity_type, entity_id)
    
    auto_hide = get_threshold(norm, 'auto_hide_threshold', DEFAULT_AUTO_HIDE_THRESHOLD)
    auto_lock = get_threshold(norm, 'auto_lock_threshold', DEFAULT_AUTO_LOCK_THRESHOLD)
    downrank = get_threshold(norm, 'downrank_after_reports', DEFAULT_DOWNRANK_THRESHOLD)
    
    # Check thresholds (highest first)
    if report_count >= auto_lock:
        apply_moderation(entity_type, entity_id, 'lock', 'auto_reports')
        apply_moderation(entity_type, entity_id, 'hide', 'auto_reports')
    elif report_count >= auto_hide:
        apply_moderation(entity_type, entity_id, 'hide', 'auto_reports')
    elif report_count >= downrank:
        apply_moderation(entity_type, entity_id, 'downrank', 'auto_reports')


def process_new_report(report: ContentReport):
    """Process a new report and trigger auto-moderation check."""
    check_and_moderate(report.entity_type, report.entity_id)


def can_user_post(user) -> tuple:
    """Check if user meets reputation requirements to post.
    
    Returns:
        (bool, str): (can_post, reason)
    """
    if not user:
        return False, "User not found"
    
    # Admins can always post
    if user.role == 'admin':
        return True, None
    
    # Get cohort norm
    cohort = f"specialty_{user.specialty}" if user.specialty else 'global'
    norm = get_cohort_norm(cohort)
    
    min_rep = get_threshold(norm, 'min_reputation_to_post', -10)
    
    if user.reputation_score < min_rep:
        return False, f"Reputation too low. Minimum required: {min_rep}"
    
    return True, None


def resolve_report(report_id: int, admin_id: int, resolution: str):
    """Resolve a content report.
    
    Args:
        report_id: ID of the report
        admin_id: ID of the admin resolving
        resolution: no_action, hide, lock, warning
    """
    report = ContentReport.query.get(report_id)
    if not report:
        return False, "Report not found"
    
    if report.status != 'open':
        return False, "Report already resolved"
    
    report.status = 'resolved'
    report.resolved_by_id = admin_id
    report.resolution = resolution
    report.resolved_at = datetime.utcnow()
    
    # Apply moderation action if needed
    if resolution in ('hide', 'lock'):
        apply_moderation(
            report.entity_type, 
            report.entity_id, 
            resolution, 
            'admin_action',
            admin_id,
            is_automated=False
        )
    
    db.session.commit()
    return True, "Report resolved"
