"""
Content Moderation System.
Handles content reports, auto-moderation, and moderation actions.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum
from app import db
import logging

logger = logging.getLogger(__name__)


class ReportReason(Enum):
    SPAM = 'spam'
    HARASSMENT = 'harassment'
    MISINFORMATION = 'misinformation'
    INAPPROPRIATE = 'inappropriate'
    COPYRIGHT = 'copyright'
    OTHER = 'other'


class ModerationAction(Enum):
    WARN = 'warn'
    HIDE = 'hide'
    DELETE = 'delete'
    BAN = 'ban'
    SUSPEND = 'suspend'


REASON_COLORS = {
    'spam': 'info',
    'harassment': 'danger',
    'misinformation': 'warning',
    'inappropriate': 'secondary',
    'copyright': 'primary',
    'other': 'dark'
}

AUTO_MODERATION_THRESHOLDS = {
    'hide_content': 3,
    'suspend_user': 5,
    'ban_user': 10,
}


class ContentModerator:
    """Content moderation manager."""
    
    @staticmethod
    def create_report(
        reporter_id: int,
        content_type: str,
        content_id: int,
        reason: str,
        description: str = None
    ) -> Optional[int]:
        """Create a content report."""
        from models import ContentReport
        
        existing = ContentReport.query.filter_by(
            reporter_id=reporter_id,
            content_type=content_type,
            content_id=content_id
        ).first()
        
        if existing:
            return None
        
        report = ContentReport(
            reporter_id=reporter_id,
            content_type=content_type,
            content_id=content_id,
            reason=reason,
            description=description,
            status='pending',
            created_at=datetime.utcnow()
        )
        db.session.add(report)
        db.session.commit()
        
        ContentModerator.check_auto_moderation(content_type, content_id)
        
        return report.id
    
    @staticmethod
    def check_auto_moderation(content_type: str, content_id: int) -> None:
        """Check if auto-moderation should be triggered."""
        from models import ContentReport
        
        report_count = ContentReport.query.filter_by(
            content_type=content_type,
            content_id=content_id,
            status='pending'
        ).count()
        
        if report_count >= AUTO_MODERATION_THRESHOLDS['hide_content']:
            ContentModerator.hide_content(content_type, content_id, reason='auto_moderation')
            logger.info(f"Auto-hid {content_type} {content_id} due to {report_count} reports")
    
    @staticmethod
    def hide_content(content_type: str, content_id: int, reason: str = None) -> bool:
        """Hide content from public view."""
        from models import Post, Comment
        
        if content_type == 'post':
            content = Post.query.get(content_id)
            if content:
                content.is_hidden = True
                content.hidden_reason = reason
                db.session.commit()
                return True
        elif content_type == 'comment':
            content = Comment.query.get(content_id)
            if content:
                content.is_hidden = True
                db.session.commit()
                return True
        
        return False
    
    @staticmethod
    def resolve_report(report_id: int, action: str, moderator_id: int, notes: str = None) -> bool:
        """Resolve a content report with a moderation action."""
        from models import ContentReport, ModerationEvent
        
        report = ContentReport.query.get(report_id)
        if not report:
            return False
        
        report.status = 'resolved'
        report.resolved_by = moderator_id
        report.resolved_at = datetime.utcnow()
        report.resolution_action = action
        report.resolution_notes = notes
        
        event = ModerationEvent(
            moderator_id=moderator_id,
            content_type=report.content_type,
            content_id=report.content_id,
            action=action,
            reason=report.reason,
            notes=notes,
            created_at=datetime.utcnow()
        )
        db.session.add(event)
        
        if action in ['hide', 'delete']:
            ContentModerator.hide_content(report.content_type, report.content_id, reason=action)
        
        db.session.commit()
        return True
    
    @staticmethod
    def dismiss_report(report_id: int, moderator_id: int) -> bool:
        """Dismiss a report as not requiring action."""
        from models import ContentReport
        
        report = ContentReport.query.get(report_id)
        if not report:
            return False
        
        report.status = 'dismissed'
        report.resolved_by = moderator_id
        report.resolved_at = datetime.utcnow()
        db.session.commit()
        
        return True
    
    @staticmethod
    def get_pending_reports(limit: int = 50) -> List:
        """Get pending reports for moderation."""
        from models import ContentReport
        return ContentReport.query.filter_by(
            status='pending'
        ).order_by(ContentReport.created_at.asc()).limit(limit).all()
    
    @staticmethod
    def get_report_stats() -> Dict:
        """Get moderation statistics."""
        from models import ContentReport
        
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        
        pending = ContentReport.query.filter_by(status='pending').count()
        resolved_today = ContentReport.query.filter(
            ContentReport.resolved_at >= today,
            ContentReport.status == 'resolved'
        ).count()
        weekly_total = ContentReport.query.filter(
            ContentReport.created_at >= week_ago
        ).count()
        
        total_resolved = ContentReport.query.filter(
            ContentReport.status.in_(['resolved', 'dismissed'])
        ).count()
        total = ContentReport.query.count()
        
        reason_counts = {}
        for reason in ReportReason:
            reason_counts[reason.value] = ContentReport.query.filter_by(
                reason=reason.value
            ).count()
        
        return {
            'pending_count': pending,
            'resolved_today': resolved_today,
            'weekly_total': weekly_total,
            'resolution_rate': (total_resolved / total * 100) if total > 0 else 100,
            'reason_stats': reason_counts,
            'total_reports': total
        }
    
    @staticmethod
    def warn_user(user_id: int, reason: str, moderator_id: int) -> bool:
        """Issue a warning to a user."""
        from models import User, ModerationEvent
        
        user = User.query.get(user_id)
        if not user:
            return False
        
        user.warning_count = (user.warning_count or 0) + 1
        
        event = ModerationEvent(
            moderator_id=moderator_id,
            target_user_id=user_id,
            action='warn',
            reason=reason,
            created_at=datetime.utcnow()
        )
        db.session.add(event)
        db.session.commit()
        
        return True
    
    @staticmethod
    def ban_user(user_id: int, reason: str, moderator_id: int, duration_days: int = None) -> bool:
        """Ban a user from the platform."""
        from models import User, ModerationEvent
        
        user = User.query.get(user_id)
        if not user or user.is_admin:
            return False
        
        user.is_banned = True
        user.banned_reason = reason
        user.banned_at = datetime.utcnow()
        
        if duration_days:
            user.banned_until = datetime.utcnow() + timedelta(days=duration_days)
        
        event = ModerationEvent(
            moderator_id=moderator_id,
            target_user_id=user_id,
            action='ban',
            reason=reason,
            created_at=datetime.utcnow()
        )
        db.session.add(event)
        db.session.commit()
        
        return True
