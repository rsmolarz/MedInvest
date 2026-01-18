"""
LTI 1.3 Platform routes for MedInvest
Enables seamless SSO between MedInvest and external learning tools like Coursebox
"""
import os
import uuid
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, redirect, url_for, render_template, flash, jsonify, session, abort
from flask_login import login_required, current_user

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

import jwt

from app import db
from models import LTITool, Course

lti_bp = Blueprint('lti', __name__, url_prefix='/lti')
logger = logging.getLogger(__name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def generate_rsa_key_pair():
    """Generate RSA key pair for LTI platform"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem


def get_platform_issuer():
    """Get the platform issuer URL"""
    if os.environ.get('REPLIT_DEPLOYMENT'):
        return f"https://{os.environ.get('REPL_SLUG')}.replit.app"
    return request.host_url.rstrip('/')


@lti_bp.route('/jwks.json')
def jwks():
    """JWKS endpoint - provides platform's public keys for tool verification"""
    tools = LTITool.query.filter_by(is_active=True).all()
    keys = []
    
    for tool in tools:
        if tool.public_key:
            try:
                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                public_key = load_pem_public_key(tool.public_key.encode('utf-8'), backend=default_backend())
                numbers = public_key.public_numbers()
                
                import base64
                def int_to_base64url(n, length):
                    return base64.urlsafe_b64encode(n.to_bytes(length, 'big')).rstrip(b'=').decode('utf-8')
                
                keys.append({
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": f"key-{tool.id}",
                    "n": int_to_base64url(numbers.n, 256),
                    "e": int_to_base64url(numbers.e, 3)
                })
            except Exception as e:
                logger.error(f"Error loading public key for tool {tool.id}: {e}")
    
    return jsonify({"keys": keys})


@lti_bp.route('/login/<int:tool_id>')
@login_required
def initiate_login(tool_id):
    """OIDC login initiation - redirects to tool's OIDC auth endpoint"""
    tool = LTITool.query.get_or_404(tool_id)
    
    if not tool.is_active:
        flash('This LTI tool is not active', 'error')
        return redirect(url_for('courses.list_courses'))
    
    state = str(uuid.uuid4())
    nonce = str(uuid.uuid4())
    
    session['lti_state'] = state
    session['lti_nonce'] = nonce
    session['lti_tool_id'] = tool_id
    
    course_id = request.args.get('course_id')
    if course_id:
        session['lti_course_id'] = course_id
    
    platform_issuer = get_platform_issuer()
    
    params = {
        'scope': 'openid',
        'response_type': 'id_token',
        'response_mode': 'form_post',
        'client_id': tool.client_id,
        'redirect_uri': url_for('lti.auth_callback', _external=True),
        'state': state,
        'nonce': nonce,
        'login_hint': str(current_user.id),
        'lti_message_hint': course_id or '',
        'prompt': 'none'
    }
    
    auth_url = f"{tool.oidc_auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return redirect(auth_url)


@lti_bp.route('/auth/callback', methods=['GET', 'POST'])
@login_required
def auth_callback():
    """Handle OIDC authentication callback from the tool"""
    state = request.values.get('state')
    
    if state != session.get('lti_state'):
        flash('Invalid state parameter', 'error')
        return redirect(url_for('courses.list_courses'))
    
    tool_id = session.get('lti_tool_id')
    tool = LTITool.query.get_or_404(tool_id)
    course_id = session.get('lti_course_id')
    
    course = None
    if course_id:
        course = Course.query.get(course_id)
    
    id_token = create_lti_message(tool, course)
    
    launch_url = tool.launch_url
    if course and course.lti_resource_link_id:
        if '?' in launch_url:
            launch_url += f"&resource_link_id={course.lti_resource_link_id}"
        else:
            launch_url += f"?resource_link_id={course.lti_resource_link_id}"
    
    session.pop('lti_state', None)
    session.pop('lti_nonce', None)
    session.pop('lti_tool_id', None)
    session.pop('lti_course_id', None)
    
    return render_template('lti/launch.html', 
                         launch_url=launch_url, 
                         id_token=id_token,
                         state=state)


def create_lti_message(tool, course=None):
    """Create LTI 1.3 launch message JWT"""
    platform_issuer = get_platform_issuer()
    nonce = session.get('lti_nonce', str(uuid.uuid4()))
    
    now = datetime.utcnow()
    
    payload = {
        "iss": platform_issuer,
        "sub": str(current_user.id),
        "aud": tool.client_id,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
        "nonce": nonce,
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": tool.deployment_id or "1",
        "https://purl.imsglobal.org/spec/lti/claim/target_link_uri": tool.launch_url,
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
            "id": course.lti_resource_link_id if course else str(uuid.uuid4()),
            "title": course.title if course else "MedInvest Course"
        },
        "https://purl.imsglobal.org/spec/lti/claim/roles": [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
        ],
        "https://purl.imsglobal.org/spec/lti/claim/context": {
            "id": str(course.id) if course else "medinvest",
            "label": course.title[:50] if course else "MedInvest",
            "title": course.title if course else "MedInvest Platform",
            "type": ["http://purl.imsglobal.org/vocab/lis/v2/course#CourseOffering"]
        },
        "name": current_user.full_name or current_user.username,
        "given_name": current_user.full_name.split()[0] if current_user.full_name else current_user.username,
        "family_name": current_user.full_name.split()[-1] if current_user.full_name and len(current_user.full_name.split()) > 1 else "",
        "email": current_user.email
    }
    
    if getattr(current_user, 'is_admin', False):
        payload["https://purl.imsglobal.org/spec/lti/claim/roles"].append(
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"
        )
    
    token = jwt.encode(
        payload,
        tool.private_key,
        algorithm="RS256",
        headers={"kid": f"key-{tool.id}"}
    )
    
    return token


@lti_bp.route('/launch/<int:course_id>')
@login_required
def launch_course(course_id):
    """Launch a course via LTI"""
    course = Course.query.get_or_404(course_id)
    
    if not course.lti_tool_id:
        flash('This course is not configured for LTI launch', 'error')
        return redirect(url_for('courses.view_course', course_id=course_id))
    
    tool = LTITool.query.get(course.lti_tool_id)
    if not tool or not tool.is_active:
        flash('LTI tool is not available', 'error')
        return redirect(url_for('courses.view_course', course_id=course_id))
    
    return redirect(url_for('lti.initiate_login', tool_id=tool.id, course_id=course_id))


@lti_bp.route('/.well-known/openid-configuration')
def openid_config():
    """OpenID Connect configuration for tools to discover platform"""
    platform_issuer = get_platform_issuer()
    
    return jsonify({
        "issuer": platform_issuer,
        "authorization_endpoint": url_for('lti.auth_callback', _external=True),
        "token_endpoint": url_for('lti.token', _external=True),
        "jwks_uri": url_for('lti.jwks', _external=True),
        "registration_endpoint": url_for('lti.register', _external=True),
        "response_types_supported": ["id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid"],
        "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        "claims_supported": ["sub", "iss", "name", "given_name", "family_name", "email"]
    })


@lti_bp.route('/token', methods=['POST'])
def token():
    """Token endpoint for LTI tool authentication"""
    return jsonify({"error": "not_implemented"}), 501


@lti_bp.route('/register', methods=['POST'])
@login_required
@admin_required
def register():
    """Dynamic tool registration endpoint"""
    return jsonify({"error": "not_implemented"}), 501
