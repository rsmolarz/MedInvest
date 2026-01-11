"""
Media Routes - Handle image and video uploads
"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from models import Post, PostMedia

media_bp = Blueprint('media', __name__, url_prefix='/media')

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
MAX_VIDEO_DURATION = 60  # 60 seconds


def allowed_file(filename, file_type='image'):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'image':
        return ext in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'video':
        return ext in ALLOWED_VIDEO_EXTENSIONS
    return False


def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def generate_unique_filename(original_filename):
    ext = get_file_extension(original_filename)
    unique_name = f"{uuid.uuid4().hex}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return f"{unique_name}.{ext}" if ext else unique_name


def ensure_upload_dirs():
    """Ensure upload directories exist"""
    base_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    for subdir in ['images', 'videos', 'thumbnails']:
        path = os.path.join(base_path, subdir)
        os.makedirs(path, exist_ok=True)
    return base_path


@media_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    return send_from_directory(upload_path, filename)


@media_bp.route('/upload', methods=['POST'])
@login_required
def upload_media():
    """Handle media upload (images and videos)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Determine file type
    ext = get_file_extension(file.filename)
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        file_type = 'image'
        max_size = MAX_IMAGE_SIZE
        subdir = 'images'
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        file_type = 'video'
        max_size = MAX_VIDEO_SIZE
        subdir = 'videos'
    else:
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Seek back to start
    
    if file_size > max_size:
        return jsonify({'error': f'File too large. Max size: {max_size // (1024*1024)}MB'}), 400
    
    # Generate unique filename and save
    base_path = ensure_upload_dirs()
    unique_filename = generate_unique_filename(file.filename)
    file_path = os.path.join(base_path, subdir, unique_filename)
    
    file.save(file_path)
    
    # Return the URL path
    url_path = f"/media/uploads/{subdir}/{unique_filename}"
    
    return jsonify({
        'success': True,
        'file_path': url_path,
        'file_type': file_type,
        'filename': unique_filename,
        'original_name': secure_filename(file.filename),
        'file_size': file_size
    })


@media_bp.route('/upload/multiple', methods=['POST'])
@login_required
def upload_multiple():
    """Handle multiple file uploads for gallery posts"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 files allowed per post'}), 400
    
    uploaded_files = []
    base_path = ensure_upload_dirs()
    
    for file in files:
        if file.filename == '':
            continue
        
        ext = get_file_extension(file.filename)
        
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            file_type = 'image'
            subdir = 'images'
        elif ext in ALLOWED_VIDEO_EXTENSIONS:
            file_type = 'video'
            subdir = 'videos'
        else:
            continue  # Skip invalid files
        
        unique_filename = generate_unique_filename(file.filename)
        file_path = os.path.join(base_path, subdir, unique_filename)
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        file.save(file_path)
        
        url_path = f"/media/uploads/{subdir}/{unique_filename}"
        
        uploaded_files.append({
            'file_path': url_path,
            'file_type': file_type,
            'filename': unique_filename,
            'file_size': file_size
        })
    
    return jsonify({
        'success': True,
        'files': uploaded_files,
        'count': len(uploaded_files)
    })
