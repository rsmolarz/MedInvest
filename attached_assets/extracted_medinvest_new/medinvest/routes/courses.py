"""
Courses Routes - Educational content
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import Course, CourseModule, CourseEnrollment

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')


@courses_bp.route('/')
def list_courses():
    """List all published courses"""
    courses = Course.query.filter_by(is_published=True)\
                         .order_by(Course.is_featured.desc(), Course.created_at.desc()).all()
    
    # Get user's enrollments
    user_enrollments = []
    if current_user.is_authenticated:
        enrollments = CourseEnrollment.query.filter_by(user_id=current_user.id).all()
        user_enrollments = [e.course_id for e in enrollments]
    
    return render_template('courses/list.html',
                         courses=courses,
                         user_enrollments=user_enrollments)


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
