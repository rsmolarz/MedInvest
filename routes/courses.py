"""
Courses Routes - Educational content
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
from app import db
from models import Course, CourseModule, CourseEnrollment


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')


@courses_bp.route('/')
def list_courses():
    """List all published courses with filtering and sorting"""
    # Filter parameters
    category = request.args.get('category')
    level = request.args.get('level')
    price_filter = request.args.get('price')
    sort_by = request.args.get('sort', 'featured')
    
    query = Course.query.filter_by(is_published=True)
    
    if category:
        query = query.filter(Course.category == category)
    
    if level:
        query = query.filter(Course.level == level)
    
    if price_filter == 'free':
        query = query.filter(Course.price == 0)
    elif price_filter == 'paid':
        query = query.filter(Course.price > 0)
    
    # Sorting
    if sort_by == 'newest':
        query = query.order_by(Course.created_at.desc())
    elif sort_by == 'price_low':
        query = query.order_by(Course.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Course.price.desc())
    elif sort_by == 'popular':
        query = query.order_by(Course.enrollment_count.desc())
    else:
        query = query.order_by(Course.is_featured.desc(), Course.created_at.desc())
    
    courses = query.all()
    
    # Get user's enrollments
    user_enrollments = []
    if current_user.is_authenticated:
        enrollments = CourseEnrollment.query.filter_by(user_id=current_user.id).all()
        user_enrollments = [e.course_id for e in enrollments]
    
    # Get unique categories and levels for filter dropdowns
    categories = db.session.query(Course.category).filter(Course.is_published==True, Course.category.isnot(None)).distinct().all()
    levels = db.session.query(Course.level).filter(Course.is_published==True, Course.level.isnot(None)).distinct().all()
    
    return render_template('courses/list.html',
                         courses=courses,
                         user_enrollments=user_enrollments,
                         categories=[c[0] for c in categories if c[0]],
                         levels=[l[0] for l in levels if l[0]],
                         selected_category=category,
                         selected_level=level,
                         price_filter=price_filter,
                         sort_by=sort_by)


@courses_bp.route('/<int:course_id>')
def view_course(course_id):
    """View course details"""
    course = Course.query.get_or_404(course_id)
    modules = CourseModule.query.filter_by(course_id=course_id)\
                                .order_by(CourseModule.order_index).all()
    
    enrollment = None
    if current_user.is_authenticated:
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course_id,
            user_id=current_user.id
        ).first()
    
    return render_template('courses/detail.html',
                         course=course,
                         modules=modules,
                         enrollment=enrollment)


@courses_bp.route('/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    """Enroll in a course"""
    course = Course.query.get_or_404(course_id)
    
    # Check if already enrolled
    existing = CourseEnrollment.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already enrolled'}), 400
    
    # In production, process payment here
    enrollment = CourseEnrollment(
        course_id=course_id,
        user_id=current_user.id,
        purchase_price=course.price,
        completed_modules=[]
    )
    
    course.enrolled_count += 1
    current_user.add_points(50)
    
    db.session.add(enrollment)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'redirect': url_for('courses.learn', course_id=course_id)
    })


@courses_bp.route('/<int:course_id>/learn')
@login_required
def learn(course_id):
    """Course learning interface"""
    course = Course.query.get_or_404(course_id)
    
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('Please enroll in this course first', 'warning')
        return redirect(url_for('courses.view_course', course_id=course_id))
    
    modules = CourseModule.query.filter_by(course_id=course_id)\
                                .order_by(CourseModule.order_index).all()
    
    # Get current module from query param or default to first
    module_id = request.args.get('module', type=int)
    current_module = None
    
    if module_id:
        current_module = CourseModule.query.get(module_id)
    elif modules:
        current_module = modules[0]
    
    return render_template('courses/learn.html',
                         course=course,
                         modules=modules,
                         current_module=current_module,
                         enrollment=enrollment)


@courses_bp.route('/<int:course_id>/module/<int:module_id>/complete', methods=['POST'])
@login_required
def complete_module(course_id, module_id):
    """Mark a module as complete"""
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if not enrollment:
        return jsonify({'error': 'Not enrolled'}), 403
    
    # Update completed modules
    completed = enrollment.completed_modules or []
    if module_id not in completed:
        completed.append(module_id)
        enrollment.completed_modules = completed
        
        # Update progress
        course = Course.query.get(course_id)
        total_modules = course.total_modules or CourseModule.query.filter_by(course_id=course_id).count()
        enrollment.progress_percent = (len(completed) / max(total_modules, 1)) * 100
        
        # Award points
        current_user.add_points(10)
        
        # Check if course completed
        if enrollment.progress_percent >= 100:
            enrollment.completed = True
            enrollment.completed_at = datetime.utcnow()
            current_user.add_points(100)  # Bonus for completing course
        
        db.session.commit()
    
    return jsonify({
        'success': True,
        'progress': enrollment.progress_percent,
        'completed': enrollment.completed
    })


@courses_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_course():
    """Create a new course (admin only)"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        instructor_name = request.form.get('instructor_name', '').strip()
        price = request.form.get('price', '0')
        duration_hours = request.form.get('duration_hours', '0')
        level = request.form.get('level', 'beginner')
        category = request.form.get('category', '').strip()
        is_featured = request.form.get('is_featured') == 'on'
        is_premium = request.form.get('is_premium') == 'on'
        cover_image_url = request.form.get('cover_image_url', '').strip()
        
        if not title:
            flash('Course title is required', 'error')
            return redirect(url_for('courses.list_courses'))
        
        course = Course(
            title=title,
            description=description,
            instructor_name=instructor_name,
            price=float(price) if price else 0,
            duration_hours=int(duration_hours) if duration_hours else 0,
            level=level,
            category=category,
            is_featured=is_featured,
            is_premium=is_premium,
            cover_image_url=cover_image_url if cover_image_url else None,
            is_published=True
        )
        
        db.session.add(course)
        db.session.commit()
        
        flash(f'Course "{title}" created successfully!', 'success')
        return redirect(url_for('courses.view_course', course_id=course.id))
    
    return redirect(url_for('courses.list_courses'))


@courses_bp.route('/<int:course_id>/add-module', methods=['POST'])
@login_required
@admin_required
def add_module(course_id):
    """Add a module to a course (admin only)"""
    course = Course.query.get_or_404(course_id)
    
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    video_url = request.form.get('video_url', '').strip()
    duration_minutes = request.form.get('duration_minutes', '0')
    
    if not title:
        flash('Module title is required', 'error')
        return redirect(url_for('courses.view_course', course_id=course_id))
    
    # Get next order index
    max_order = db.session.query(db.func.max(CourseModule.order_index)).filter_by(course_id=course_id).scalar() or 0
    
    module = CourseModule(
        course_id=course_id,
        title=title,
        content=content,
        video_url=video_url if video_url else None,
        duration_minutes=int(duration_minutes) if duration_minutes else 0,
        order_index=max_order + 1
    )
    
    db.session.add(module)
    course.total_modules = (course.total_modules or 0) + 1
    db.session.commit()
    
    flash(f'Module "{title}" added!', 'success')
    return redirect(url_for('courses.view_course', course_id=course_id))
