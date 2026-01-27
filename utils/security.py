"""
Security Utilities - XSS protection, PII masking, CSRF validation, and more
"""
import re
import os
import hashlib
import secrets
import logging
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, session, abort, g

logger = logging.getLogger(__name__)

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    logger.warning("Bleach library not available. Using basic HTML sanitization.")

ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'em', 
    'i', 'li', 'ol', 'p', 'pre', 'strong', 'ul', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'span', 'div', 'table', 'thead', 'tbody', 
    'tr', 'th', 'td', 'img', 'hr'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'abbr': ['title'],
    'acronym': ['title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*': ['class', 'id', 'style']
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

PII_PATTERNS = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    'npi': r'\b\d{10}\b',
}


def sanitize_html(content: str, allow_images: bool = False) -> str:
    """
    Sanitize HTML content to prevent XSS attacks
    
    Args:
        content: Raw HTML content
        allow_images: Whether to allow img tags
        
    Returns:
        Sanitized HTML string
    """
    if not content:
        return ''
    
    tags = ALLOWED_TAGS.copy()
    attrs = ALLOWED_ATTRIBUTES.copy()
    
    if not allow_images and 'img' in tags:
        tags.remove('img')
        if 'img' in attrs:
            del attrs['img']
    
    if BLEACH_AVAILABLE:
        return bleach.clean(
            content,
            tags=tags,
            attributes=attrs,
            protocols=ALLOWED_PROTOCOLS,
            strip=True
        )
    else:
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<object[^>]*>.*?</object>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<embed[^>]*>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
        content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
        return content


def escape_for_log(text: str) -> str:
    """Escape text for safe logging (prevent log injection)"""
    if not text:
        return ''
    return text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def mask_pii(text: str, mask_char: str = '*') -> str:
    """
    Mask personally identifiable information in text
    
    Args:
        text: Text that may contain PII
        mask_char: Character to use for masking
        
    Returns:
        Text with PII masked
    """
    if not text:
        return ''
    
    masked = text
    
    def email_mask(match):
        email = match.group(0)
        parts = email.split('@')
        if len(parts[0]) > 2:
            return parts[0][0] + mask_char * (len(parts[0]) - 2) + parts[0][-1] + '@' + parts[1]
        return mask_char * len(parts[0]) + '@' + parts[1]
    
    def phone_mask(match):
        return mask_char * 6 + match.group(0)[-4:]
    
    def ssn_mask(match):
        return mask_char * 7 + match.group(0)[-4:]
    
    def card_mask(match):
        return mask_char * 12 + match.group(0).replace('-', '').replace(' ', '')[-4:]
    
    def ip_mask(match):
        return mask_char * 8 + '.' + match.group(0).split('.')[-1]
    
    masked = re.sub(PII_PATTERNS['email'], email_mask, masked)
    masked = re.sub(PII_PATTERNS['phone'], phone_mask, masked)
    masked = re.sub(PII_PATTERNS['ssn'], ssn_mask, masked)
    masked = re.sub(PII_PATTERNS['credit_card'], card_mask, masked)
    masked = re.sub(PII_PATTERNS['ip_address'], ip_mask, masked)
    
    return masked


def generate_csrf_token() -> str:
    """Generate a CSRF token for the session"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token(token: str) -> bool:
    """Validate a CSRF token against the session"""
    session_token = session.get('_csrf_token')
    if not session_token or not token:
        return False
    return secrets.compare_digest(session_token, token)


def csrf_protect():
    """
    Decorator to protect routes from CSRF attacks
    Validates CSRF token on POST, PUT, DELETE, PATCH requests
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
                
                if not token:
                    logger.warning(f"CSRF token missing for {request.path}")
                    abort(400, description="CSRF token missing")
                
                if not validate_csrf_token(token):
                    logger.warning(f"Invalid CSRF token for {request.path}")
                    abort(400, description="Invalid CSRF token")
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hash sensitive data for storage (one-way)
    
    Args:
        data: Sensitive data to hash
        salt: Optional salt (uses env var if not provided)
        
    Returns:
        Hashed string
    """
    if salt is None:
        salt = os.environ.get('SESSION_SECRET', 'default-salt')
    
    return hashlib.sha256((salt + data).encode()).hexdigest()


def encrypt_at_rest(data: str) -> str:
    """
    Encrypt data for storage at rest (HIPAA compliance)
    Uses Fernet symmetric encryption
    
    Args:
        data: Data to encrypt
        
    Returns:
        Encrypted string (base64 encoded)
    """
    try:
        from cryptography.fernet import Fernet
        
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            key = Fernet.generate_key().decode()
            logger.warning("No ENCRYPTION_KEY set. Using temporary key. Set ENCRYPTION_KEY env var for production.")
        
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.encrypt(data.encode()).decode()
    except ImportError:
        logger.warning("Cryptography library not available. Data not encrypted.")
        return data
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return data


def decrypt_at_rest(encrypted_data: str) -> str:
    """
    Decrypt data that was encrypted at rest
    
    Args:
        encrypted_data: Encrypted string (base64 encoded)
        
    Returns:
        Decrypted string
    """
    try:
        from cryptography.fernet import Fernet
        
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            logger.error("No ENCRYPTION_KEY set. Cannot decrypt.")
            return encrypted_data
        
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(encrypted_data.encode()).decode()
    except ImportError:
        logger.warning("Cryptography library not available.")
        return encrypted_data
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return encrypted_data


def get_device_fingerprint() -> str:
    """
    Generate a device fingerprint from request headers
    Used for suspicious activity detection
    """
    components = [
        request.headers.get('User-Agent', ''),
        request.headers.get('Accept-Language', ''),
        request.headers.get('Accept-Encoding', ''),
        request.headers.get('Accept', ''),
    ]
    fingerprint_data = '|'.join(components)
    return hashlib.md5(fingerprint_data.encode()).hexdigest()


def log_security_event(event_type: str, user_id: Optional[int], details: Dict[str, Any]):
    """
    Log security-related events for audit trail
    
    Args:
        event_type: Type of security event (login_failed, suspicious_activity, etc.)
        user_id: User ID if known
        details: Additional event details
    """
    from models import UserActivity
    
    masked_details = {k: mask_pii(str(v)) if isinstance(v, str) else v for k, v in details.items()}
    
    logger.info(f"SECURITY_EVENT: type={event_type}, user={user_id}, details={masked_details}")
    
    try:
        activity = UserActivity(
            user_id=user_id,
            activity_type=event_type,
            details=str(masked_details),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        from app import db
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging security event: {e}")


def secure_headers_middleware(response):
    """
    Add security headers to response
    Call this in after_request hook
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response
