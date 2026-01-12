from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, DirectMessageThread, DirectMessageParticipant, DirectMessage
from datetime import datetime

dm_bp = Blueprint('dm', __name__, url_prefix='/messages')


def get_or_create_thread(user1_id, user2_id):
    """Get existing thread between two users or create a new one"""
    thread = DirectMessageThread.query.join(DirectMessageParticipant).filter(
        DirectMessageParticipant.user_id == user1_id
    ).join(DirectMessageParticipant, DirectMessageThread.id == DirectMessageParticipant.thread_id, isouter=True).filter(
        DirectMessageParticipant.user_id == user2_id
    ).first()
    
    if not thread:
        subq1 = db.session.query(DirectMessageParticipant.thread_id).filter(
            DirectMessageParticipant.user_id == user1_id
        ).subquery()
        subq2 = db.session.query(DirectMessageParticipant.thread_id).filter(
            DirectMessageParticipant.user_id == user2_id
        ).subquery()
        
        thread = DirectMessageThread.query.filter(
            DirectMessageThread.id.in_(subq1),
            DirectMessageThread.id.in_(subq2)
        ).first()
    
    if not thread:
        thread = DirectMessageThread()
        db.session.add(thread)
        db.session.flush()
        
        p1 = DirectMessageParticipant(thread_id=thread.id, user_id=user1_id)
        p2 = DirectMessageParticipant(thread_id=thread.id, user_id=user2_id)
        db.session.add(p1)
        db.session.add(p2)
        db.session.commit()
    
    return thread


@dm_bp.route('/')
@login_required
def inbox():
    """Show all message threads for current user"""
    threads_data = []
    
    participations = DirectMessageParticipant.query.filter_by(user_id=current_user.id).all()
    
    for participation in participations:
        thread = participation.thread
        other_participant = DirectMessageParticipant.query.filter(
            DirectMessageParticipant.thread_id == thread.id,
            DirectMessageParticipant.user_id != current_user.id
        ).first()
        
        if other_participant:
            other_user = other_participant.user
            last_message = DirectMessage.query.filter_by(thread_id=thread.id).order_by(DirectMessage.created_at.desc()).first()
            
            unread_count = DirectMessage.query.filter(
                DirectMessage.thread_id == thread.id,
                DirectMessage.sender_id != current_user.id,
                DirectMessage.read_at == None
            ).count()
            
            threads_data.append({
                'thread': thread,
                'other_user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
    
    threads_data.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else x['thread'].created_at, reverse=True)
    
    return render_template('dm/inbox.html', threads=threads_data)


@dm_bp.route('/thread/<int:thread_id>')
@login_required
def thread(thread_id):
    """View a specific message thread"""
    participation = DirectMessageParticipant.query.filter_by(
        thread_id=thread_id,
        user_id=current_user.id
    ).first_or_404()
    
    thread = participation.thread
    
    other_participant = DirectMessageParticipant.query.filter(
        DirectMessageParticipant.thread_id == thread_id,
        DirectMessageParticipant.user_id != current_user.id
    ).first()
    
    other_user = other_participant.user if other_participant else None
    
    messages = DirectMessage.query.filter_by(thread_id=thread_id).order_by(DirectMessage.created_at.asc()).all()
    
    DirectMessage.query.filter(
        DirectMessage.thread_id == thread_id,
        DirectMessage.sender_id != current_user.id,
        DirectMessage.read_at == None
    ).update({'read_at': datetime.utcnow()})
    db.session.commit()
    
    return render_template('dm/thread.html', thread=thread, messages=messages, other_user=other_user)


@dm_bp.route('/thread/<int:thread_id>/send', methods=['POST'])
@login_required
def send_message(thread_id):
    """Send a message in a thread"""
    participation = DirectMessageParticipant.query.filter_by(
        thread_id=thread_id,
        user_id=current_user.id
    ).first_or_404()
    
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Message cannot be empty', 'error')
        return redirect(url_for('dm.thread', thread_id=thread_id))
    
    message = DirectMessage(
        thread_id=thread_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    return redirect(url_for('dm.thread', thread_id=thread_id))


@dm_bp.route('/new/<int:user_id>')
@login_required
def new_thread(user_id):
    """Start or continue a conversation with a user"""
    if user_id == current_user.id:
        flash("You can't message yourself", 'error')
        return redirect(url_for('dm.inbox'))
    
    other_user = User.query.get_or_404(user_id)
    thread = get_or_create_thread(current_user.id, user_id)
    
    return redirect(url_for('dm.thread', thread_id=thread.id))


@dm_bp.route('/api/unread-count')
@login_required
def unread_count():
    """Get total unread message count for current user"""
    participations = DirectMessageParticipant.query.filter_by(user_id=current_user.id).all()
    thread_ids = [p.thread_id for p in participations]
    
    count = DirectMessage.query.filter(
        DirectMessage.thread_id.in_(thread_ids),
        DirectMessage.sender_id != current_user.id,
        DirectMessage.read_at == None
    ).count() if thread_ids else 0
    
    return jsonify({'count': count})
