"""
Connections Routes - Friend/Connection request management
"""
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models import User, Connection, NotificationType
from routes.notifications import create_notification

connections_bp = Blueprint('connections', __name__, url_prefix='/connections')


@connections_bp.route('/')
@login_required
def index():
    """View all connections"""
    connections = db.session.query(Connection, User).join(
        User,
        db.or_(
            db.and_(Connection.requester_id == current_user.id, Connection.addressee_id == User.id),
            db.and_(Connection.addressee_id == current_user.id, Connection.requester_id == User.id)
        )
    ).filter(
        db.or_(Connection.requester_id == current_user.id, Connection.addressee_id == current_user.id),
        Connection.status == 'accepted'
    ).all()
    
    pending_received = Connection.query.filter_by(
        addressee_id=current_user.id,
        status='pending'
    ).all()
    
    pending_sent = Connection.query.filter_by(
        requester_id=current_user.id,
        status='pending'
    ).all()
    
    return render_template('connections/index.html',
                         connections=connections,
                         pending_received=pending_received,
                         pending_sent=pending_sent)


@connections_bp.route('/send/<int:user_id>', methods=['POST'])
@login_required
def send_request(user_id):
    """Send a connection request"""
    if user_id == current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Cannot connect with yourself'}), 400
        flash('You cannot connect with yourself.', 'warning')
        return redirect(url_for('main.profile', user_id=user_id))
    
    target_user = User.query.get_or_404(user_id)
    
    existing = Connection.query.filter(
        db.or_(
            db.and_(Connection.requester_id == current_user.id, Connection.addressee_id == user_id),
            db.and_(Connection.requester_id == user_id, Connection.addressee_id == current_user.id)
        )
    ).first()
    
    if existing:
        if existing.status == 'accepted':
            msg = 'You are already connected with this user.'
        elif existing.status == 'pending':
            if existing.requester_id == current_user.id:
                msg = 'Connection request already sent.'
            else:
                msg = 'This user already sent you a request. Check your pending requests.'
        else:
            existing.status = 'pending'
            existing.requester_id = current_user.id
            existing.addressee_id = user_id
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            
            create_notification(
                user_id=user_id,
                notification_type=NotificationType.CONNECTION_REQUEST,
                title='Connection Request',
                message=f'{current_user.full_name} wants to connect with you',
                actor_id=current_user.id,
                url=url_for('connections.index')
            )
            db.session.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'status': 'pending'})
            flash('Connection request sent!', 'success')
            return redirect(url_for('main.profile', user_id=user_id))
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg, 'status': existing.status}), 400
        flash(msg, 'info')
        return redirect(url_for('main.profile', user_id=user_id))
    
    connection = Connection(
        requester_id=current_user.id,
        addressee_id=user_id,
        status='pending'
    )
    db.session.add(connection)
    
    create_notification(
        user_id=user_id,
        notification_type=NotificationType.CONNECTION_REQUEST,
        title='Connection Request',
        message=f'{current_user.full_name} wants to connect with you',
        actor_id=current_user.id,
        url=url_for('connections.index')
    )
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': 'pending'})
    flash('Connection request sent!', 'success')
    return redirect(url_for('main.profile', user_id=user_id))


@connections_bp.route('/accept/<int:connection_id>', methods=['POST'])
@login_required
def accept_request(connection_id):
    """Accept a connection request"""
    connection = Connection.query.filter_by(
        id=connection_id,
        addressee_id=current_user.id,
        status='pending'
    ).first_or_404()
    
    connection.status = 'accepted'
    connection.updated_at = datetime.utcnow()
    
    requester = User.query.get(connection.requester_id)
    create_notification(
        user_id=connection.requester_id,
        notification_type=NotificationType.CONNECTION_ACCEPTED,
        title='Connection Accepted',
        message=f'{current_user.full_name} accepted your connection request',
        actor_id=current_user.id,
        url=url_for('main.profile', user_id=current_user.id)
    )
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash(f'You are now connected with {requester.full_name}!', 'success')
    return redirect(url_for('connections.index'))


@connections_bp.route('/decline/<int:connection_id>', methods=['POST'])
@login_required
def decline_request(connection_id):
    """Decline a connection request"""
    connection = Connection.query.filter_by(
        id=connection_id,
        addressee_id=current_user.id,
        status='pending'
    ).first_or_404()
    
    connection.status = 'declined'
    connection.updated_at = datetime.utcnow()
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('Connection request declined.', 'info')
    return redirect(url_for('connections.index'))


@connections_bp.route('/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_connection(user_id):
    """Remove a connection"""
    connection = Connection.query.filter(
        db.or_(
            db.and_(Connection.requester_id == current_user.id, Connection.addressee_id == user_id),
            db.and_(Connection.requester_id == user_id, Connection.addressee_id == current_user.id)
        ),
        Connection.status == 'accepted'
    ).first_or_404()
    
    db.session.delete(connection)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('Connection removed.', 'info')
    return redirect(url_for('connections.index'))


@connections_bp.route('/cancel/<int:connection_id>', methods=['POST'])
@login_required
def cancel_request(connection_id):
    """Cancel a pending connection request"""
    connection = Connection.query.filter_by(
        id=connection_id,
        requester_id=current_user.id,
        status='pending'
    ).first_or_404()
    
    db.session.delete(connection)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('Connection request cancelled.', 'info')
    return redirect(url_for('connections.index'))


@connections_bp.route('/status/<int:user_id>')
@login_required
def get_status(user_id):
    """Get connection status with a user"""
    if user_id == current_user.id:
        return jsonify({'status': 'self'})
    
    connection = Connection.query.filter(
        db.or_(
            db.and_(Connection.requester_id == current_user.id, Connection.addressee_id == user_id),
            db.and_(Connection.requester_id == user_id, Connection.addressee_id == current_user.id)
        )
    ).first()
    
    if not connection:
        return jsonify({'status': 'none', 'connection_id': None})
    
    is_requester = connection.requester_id == current_user.id
    return jsonify({
        'status': connection.status,
        'connection_id': connection.id,
        'is_requester': is_requester
    })
