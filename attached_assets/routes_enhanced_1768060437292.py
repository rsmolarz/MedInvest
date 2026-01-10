"""
Enhanced Routes for MedInvest Platform
New features: Anonymous posting, Trending topics, Specialty rooms, Achievements
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import app, db
from models_enhanced import (
    User, Post, Comment, Like, InvestmentRoom, RoomMembership,
    Achievement, UserAchievement, TrendingTopic, NewsletterSubscription
)
from datetime import datetime
import json


# ============================================================================
# SPECIALTY INVESTMENT ROOMS
# ============================================================================

@app.route('/rooms')
@login_required
def investment_rooms():
    """List all investment rooms"""
    # Get all active rooms
    rooms = InvestmentRoom.query.filter_by(is_active=True).all()
    
    # Categorize rooms
    specialty_rooms = [r for r in rooms if r.room_type == 'specialty']
    career_stage_rooms = [r for r in rooms if r.room_type == 'career_stage']
    topic_rooms = [r for r in rooms if r.room_type == 'topic']
    
    # Get user's room memberships
    user_rooms = [m.room for m in current_user.room_memberships.filter_by(is_active=True).all()]
    
    return render_template('rooms.html',
                         specialty_rooms=specialty_rooms,
                         career_stage_rooms=career_stage_rooms,
                         topic_rooms=topic_rooms,
                         user_rooms=user_rooms)


@app.route('/room/<int:room_id>')
@login_required
def room_detail(room_id):
    """View a specific investment room"""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    # Check if user is a member
    is_member = room.is_member(current_user)
    
    # Get room posts
    posts = Post.query.filter_by(room_id=room_id, is_published=True)\
                      .order_by(Post.created_at.desc())\
                      .limit(20).all()
    
    # Get room stats
    stats = {
        'members': room.member_count(),
        'posts': room.post_count(),
        'is_member': is_member
    }
    
    return render_template('room_detail.html',
                         room=room,
                         posts=posts,
                         stats=stats)


@app.route('/room/<int:room_id>/join', methods=['POST'])
@login_required
def join_room(room_id):
    """Join an investment room"""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    if room.is_member(current_user):
        return jsonify({'success': False, 'error': 'Already a member'}), 400
    
    membership = RoomMembership(user_id=current_user.id, room_id=room_id)
    db.session.add(membership)
    db.session.commit()
    
    # Award achievement for joining first room
    first_room_achievement = Achievement.query.filter_by(name='Community Explorer').first()
    if first_room_achievement:
        current_user.award_achievement(first_room_achievement.id)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'members': room.member_count()
    })


@app.route('/room/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_room(room_id):
    """Leave an investment room"""
    membership = RoomMembership.query.filter_by(
        user_id=current_user.id,
        room_id=room_id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 400
    
    membership.is_active = False
    db.session.commit()
    
    room = InvestmentRoom.query.get(room_id)
    return jsonify({
        'success': True,
        'members': room.member_count()
    })


@app.route('/room/<int:room_id>/post', methods=['POST'])
@login_required
def create_room_post(room_id):
    """Create a post in a specific room"""
    room = InvestmentRoom.query.get_or_404(room_id)
    
    # Check if user is a member
    if not room.is_member(current_user):
        flash('You must join the room to post', 'error')
        return redirect(url_for('room_detail', room_id=room_id))
    
    content = request.form.get('content', '').strip()
    post_type = request.form.get('post_type', 'general')
    tags = request.form.get('tags', '')
    is_anonymous = request.form.get('anonymous') == 'true'
    
    if not content:
        flash('Post content cannot be empty', 'error')
        return redirect(url_for('room_detail', room_id=room_id))
    
    # Create the post
    post = Post(
        author_id=current_user.id,
        content=content,
        post_type=post_type,
        tags=tags,
        room_id=room_id,
        is_anonymous=is_anonymous
    )
    
    # Generate anonymous name if needed
    if is_anonymous:
        post.anonymous_name = f"{current_user.specialty} • {current_user.location or 'USA'}"
    
    db.session.add(post)
    
    # Update trending topics
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        TrendingTopic.update_trending(tag_list, current_user.id)
    
    # Award achievement for first post
    first_post_achievement = Achievement.query.filter_by(name='First Post').first()
    if first_post_achievement and current_user.posts.count() == 0:
        current_user.award_achievement(first_post_achievement.id)
    
    db.session.commit()
    
    flash('Post created successfully!', 'success')
    return redirect(url_for('room_detail', room_id=room_id))


# ============================================================================
# ANONYMOUS POSTING
# ============================================================================

@app.route('/create_anonymous_post', methods=['POST'])
@login_required
def create_anonymous_post():
    """Create an anonymous post in the main feed"""
    content = request.form.get('content', '').strip()
    post_type = request.form.get('post_type', 'general')
    tags = request.form.get('tags', '')
    
    if not content:
        flash('Post content cannot be empty', 'error')
        return redirect(url_for('dashboard'))
    
    # Create anonymous post
    post = Post(
        author_id=current_user.id,
        content=content,
        post_type=post_type,
        tags=tags,
        is_anonymous=True,
        anonymous_name=f"{current_user.specialty} • {current_user.location or 'USA'}"
    )
    
    db.session.add(post)
    
    # Update trending topics
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        TrendingTopic.update_trending(tag_list, current_user.id)
    
    db.session.commit()
    
    flash('Anonymous post created successfully!', 'success')
    return redirect(url_for('dashboard'))


# ============================================================================
# TRENDING TOPICS
# ============================================================================

@app.route('/trending')
@login_required
def trending_topics():
    """View trending topics and discussions"""
    # Get top trending topics
    trending = TrendingTopic.get_trending(limit=20)
    
    # Get posts for each trending topic
    trending_posts = {}
    for topic in trending:
        posts = Post.query.filter(
            Post.tags.contains(topic.tag),
            Post.is_published == True
        ).order_by(Post.created_at.desc()).limit(3).all()
        trending_posts[topic.tag] = posts
    
    return render_template('trending.html',
                         trending=trending,
                         trending_posts=trending_posts)


@app.route('/tag/<tag_name>')
@login_required
def view_tag(tag_name):
    """View all posts with a specific tag"""
    posts = Post.query.filter(
        Post.tags.contains(tag_name),
        Post.is_published == True
    ).order_by(Post.created_at.desc()).all()
    
    # Update the tag's view count
    topic = TrendingTopic.query.filter_by(tag=tag_name.lower()).first()
    if topic:
        topic.mention_count += 1
        db.session.commit()
    
    return render_template('tag_posts.html',
                         tag=tag_name,
                         posts=posts)


@app.route('/api/trending', methods=['GET'])
@login_required
def api_trending():
    """API endpoint for trending topics"""
    limit = request.args.get('limit', 10, type=int)
    trending = TrendingTopic.get_trending(limit=limit)
    
    return jsonify({
        'trending': [{
            'tag': t.tag,
            'count': t.mention_count,
            'score': round(t.trend_score, 2)
        } for t in trending]
    })


# ============================================================================
# ACHIEVEMENTS & GAMIFICATION
# ============================================================================

@app.route('/achievements')
@login_required
def achievements():
    """View all achievements and user progress"""
    # Get all achievements categorized
    all_achievements = Achievement.query.filter_by(is_active=True).all()
    
    categories = {}
    for achievement in all_achievements:
        cat = achievement.category or 'other'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'achievement': achievement,
            'earned': current_user.has_achievement(achievement.id),
            'earned_at': None
        })
    
    # Get user's earned achievements with dates
    user_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
    earned_map = {ua.achievement_id: ua.earned_at for ua in user_achievements}
    
    # Update earned dates
    for cat in categories:
        for item in categories[cat]:
            if item['earned']:
                item['earned_at'] = earned_map.get(item['achievement'].id)
    
    # Calculate progress
    total_achievements = len(all_achievements)
    earned_count = len(user_achievements)
    progress_percent = int((earned_count / total_achievements * 100)) if total_achievements > 0 else 0
    
    # Leaderboard - top users by points
    leaderboard = User.query.filter(
        User.account_active == True
    ).order_by(User.points.desc()).limit(10).all()
    
    return render_template('achievements.html',
                         categories=categories,
                         earned_count=earned_count,
                         total_achievements=total_achievements,
                         progress_percent=progress_percent,
                         user_points=current_user.points,
                         leaderboard=leaderboard)


@app.route('/api/check_achievements', methods=['POST'])
@login_required
def check_achievements():
    """Check if user has earned new achievements"""
    newly_earned = []
    
    # Check various achievement conditions
    achievements_to_check = Achievement.query.filter_by(is_active=True).all()
    
    for achievement in achievements_to_check:
        if current_user.has_achievement(achievement.id):
            continue
        
        # Parse requirements
        try:
            requirements = json.loads(achievement.requirements) if achievement.requirements else {}
        except:
            requirements = {}
        
        earned = False
        
        # Check specific requirements
        if 'modules_completed' in requirements:
            from models_enhanced import UserProgress
            completed = UserProgress.query.filter_by(
                user_id=current_user.id,
                completed=True
            ).count()
            if completed >= requirements['modules_completed']:
                earned = True
        
        if 'posts_created' in requirements:
            if current_user.posts.count() >= requirements['posts_created']:
                earned = True
        
        if 'followers' in requirements:
            if current_user.followers_count() >= requirements['followers']:
                earned = True
        
        if 'rooms_joined' in requirements:
            active_memberships = current_user.room_memberships.filter_by(is_active=True).count()
            if active_memberships >= requirements['rooms_joined']:
                earned = True
        
        # Award if earned
        if earned:
            current_user.award_achievement(achievement.id)
            newly_earned.append({
                'name': achievement.name,
                'description': achievement.description,
                'points': achievement.points,
                'icon': achievement.icon
            })
    
    if newly_earned:
        db.session.commit()
    
    return jsonify({
        'success': True,
        'achievements': newly_earned,
        'total_points': current_user.points
    })


# ============================================================================
# NEWSLETTER SUBSCRIPTION
# ============================================================================

@app.route('/newsletter/subscribe', methods=['POST'])
@login_required
def subscribe_newsletter():
    """Subscribe to newsletter"""
    existing = NewsletterSubscription.query.filter_by(user_id=current_user.id).first()
    
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.subscribed_at = datetime.utcnow()
            existing.unsubscribed_at = None
    else:
        subscription = NewsletterSubscription(user_id=current_user.id)
        db.session.add(subscription)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Subscribed to newsletter'})


@app.route('/newsletter/unsubscribe', methods=['POST'])
@login_required
def unsubscribe_newsletter():
    """Unsubscribe from newsletter"""
    subscription = NewsletterSubscription.query.filter_by(user_id=current_user.id).first()
    
    if subscription:
        subscription.is_active = False
        subscription.unsubscribed_at = datetime.utcnow()
        db.session.commit()
    
    return jsonify({'success': True, 'message': 'Unsubscribed from newsletter'})


@app.route('/newsletter/preferences', methods=['GET', 'POST'])
@login_required
def newsletter_preferences():
    """Manage newsletter preferences"""
    subscription = NewsletterSubscription.query.filter_by(user_id=current_user.id).first()
    
    if not subscription:
        subscription = NewsletterSubscription(user_id=current_user.id)
        db.session.add(subscription)
        db.session.commit()
    
    if request.method == 'POST':
        subscription.weekly_digest = request.form.get('weekly_digest') == 'on'
        subscription.trending_topics = request.form.get('trending_topics') == 'on'
        subscription.investment_opportunities = request.form.get('investment_opportunities') == 'on'
        subscription.specialty_updates = request.form.get('specialty_updates') == 'on'
        
        db.session.commit()
        flash('Newsletter preferences updated', 'success')
        return redirect(url_for('profile'))
    
    return render_template('newsletter_preferences.html', subscription=subscription)


# ============================================================================
# ENHANCED DASHBOARD WITH NEW FEATURES
# ============================================================================

@app.route('/dashboard_enhanced')
@login_required
def dashboard_enhanced():
    """Enhanced dashboard with trending topics, rooms, and achievements"""
    try:
        # Get feed posts (from following + public)
        following_ids = [f.following_id for f in current_user.following.all()]
        following_ids.append(current_user.id)
        
        feed_posts = Post.query.filter(
            Post.is_published == True
        ).order_by(Post.created_at.desc()).limit(10).all()
        
        # Get trending topics
        trending = TrendingTopic.get_trending(limit=5)
        
        # Get user's rooms
        user_rooms = [m.room for m in current_user.room_memberships.filter_by(is_active=True).limit(5).all()]
        
        # Get suggested rooms (based on specialty)
        suggested_rooms = InvestmentRoom.query.filter(
            InvestmentRoom.specialty == current_user.specialty,
            InvestmentRoom.is_active == True
        ).limit(3).all()
        
        # Get recent achievements
        recent_achievements = UserAchievement.query.filter_by(
            user_id=current_user.id
        ).order_by(UserAchievement.earned_at.desc()).limit(3).all()
        
        # User stats
        stats = {
            'posts_count': current_user.posts.count(),
            'followers_count': current_user.followers_count(),
            'following_count': current_user.following_count(),
            'points': current_user.points,
            'achievements': current_user.achievements.count()
        }
        
        return render_template('dashboard_enhanced.html',
                             posts=feed_posts,
                             trending=trending,
                             user_rooms=user_rooms,
                             suggested_rooms=suggested_rooms,
                             recent_achievements=recent_achievements,
                             stats=stats)
    except Exception as e:
        import logging
        logging.error(f"Dashboard enhanced error: {e}")
        # Fallback to simple view
        return render_template('dashboard_enhanced.html',
                             posts=[],
                             trending=[],
                             user_rooms=[],
                             suggested_rooms=[],
                             recent_achievements=[],
                             stats={'posts_count': 0, 'followers_count': 0, 
                                   'following_count': 0, 'points': 0, 'achievements': 0})
