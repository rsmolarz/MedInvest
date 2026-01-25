"""
InvestDocs Integration Module
=============================
This module handles the integration of InvestmentVault (InvestDocs) into MedInvest.
Supports both standalone and embedded modes with multiple integration phases.

Phases:
- Phase 1: Iframe Embedding (Current)
- Phase 2: SSO Integration
- Phase 3: Database Integration
- Phase 4: Feature Integration
"""

from flask import Blueprint, render_template, jsonify, request, session, current_app
from flask_login import login_required, current_user
import requests
import os
from datetime import timedelta
from functools import wraps
import logging
from flask_jwt_extended import create_access_token

logger = logging.getLogger(__name__)

# Blueprint Configuration
investdocs_bp = Blueprint(
    'investdocs',
    __name__,
    url_prefix='/investdocs',
    template_folder='../templates',
    static_folder='../static'
)

# Configuration
INVESTDOCS_STANDALONE_URL = os.environ.get('INVESTDOCS_URL', 'http://localhost:3000')
INVESTDOCS_INTERNAL_URL = os.environ.get('INVESTDOCS_INTERNAL_URL', 'http://localhost:3000')
INVESTDOCS_MODE = os.environ.get('INVESTDOCS_MODE', 'iframe')
INVESTDOCS_PROXY_API = os.environ.get('INVESTDOCS_PROXY_API', True)

# ===========================
# PHASE 1: IFRAME EMBEDDING
# ===========================

@investdocs_bp.route('/', methods=['GET'])
@login_required
def dashboard():
    """Display InvestDocs dashboard - Phase 1: Serves iframe embedding"""
    context = {
        'investdocs_url': INVESTDOCS_STANDALONE_URL,
        'user_id': current_user.id,
        'mode': INVESTDOCS_MODE,
        'has_documents': False,
    }
    return render_template('investdocs/iframe.html', **context)


# ===========================
# PHASE 2: SSO INTEGRATION
# ===========================

def create_sso_token(user):
    """Create JWT token for SSO with InvestmentVault - Phase 2: SSO integration"""
    try:
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(hours=24),
            additional_claims={
                'email': user.email,
                'username': user.username,
                'avatar': user.avatar_url if hasattr(user, 'avatar_url') else None
            }
        )
        return token
    except ImportError:
        logger.error("flask_jwt_extended not installed. Phase 2 SSO not available.")
        return None


@investdocs_bp.route('/auth/sync', methods=['POST'])
@login_required
def sync_auth():
    """Synchronize authentication between MedInvest and InvestmentVault - Phase 2: SSO Integration"""
    token = create_sso_token(current_user)

    if not token:
        return jsonify({'error': 'SSO not configured'}), 500

    return jsonify({
        'success': True,
        'token': token,
        'user_id': current_user.id,
        'email': current_user.email,
        'username': current_user.username if hasattr(current_user, 'username') else None
    }), 200


@investdocs_bp.route('/embedded', methods=['GET'])
@login_required
def embedded():
    """Serve InvestDocs as embedded React component - Phase 2: Embedded integration"""
    token = create_sso_token(current_user)
    context = {
        'token': token,
        'user_id': current_user.id,
        'mode': 'embedded',
        'investdocs_api': '/investdocs/api'
    }
    return render_template('investdocs/embedded.html', **context)


# ===========================
# PHASE 2: API PROXY
# ===========================

@investdocs_bp.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@login_required
def proxy_api(path):
    """Proxy API calls from frontend to InvestmentVault backend - Phase 2: API Integration"""
    if not INVESTDOCS_PROXY_API:
        return jsonify({'error': 'API proxy disabled'}), 403

    try:
        url = f"{INVESTDOCS_INTERNAL_URL}/api/{path}"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MedInvest-InvestDocs-Proxy/1.0'
        }

        token = create_sso_token(current_user)
        if token:
            headers['Authorization'] = f'Bearer {token}'

        headers['X-Forwarded-For'] = request.remote_addr
        headers['X-Forwarded-User-Id'] = str(current_user.id)
        headers['X-Forwarded-Email'] = current_user.email

        params = request.args.to_dict() if request.method in ['GET', 'DELETE'] else None

        response = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            json=request.get_json() if request.method in ['POST', 'PUT', 'PATCH'] else None,
            params=params,
            timeout=30
        )

        logger.info(f"InvestDocs API request: {request.method} {path} -> {response.status_code}")
        return jsonify(response.json()) if response.text else '', response.status_code

    except requests.exceptions.ConnectionError:
        logger.error(f"InvestDocs server connection error: {url}")
        return jsonify({'error': 'InvestDocs service unavailable'}), 503
    except requests.exceptions.Timeout:
        logger.error(f"InvestDocs server timeout: {url}")
        return jsonify({'error': 'InvestDocs request timeout'}), 504
    except Exception as e:
        logger.error(f"InvestDocs proxy error: {str(e)}")
        return jsonify({'error': 'Proxy error', 'details': str(e)}), 500


# ===========================
# PHASE 3: DATABASE INTEGRATION
# ===========================

@investdocs_bp.route('/sync/documents', methods=['GET', 'POST'])
@login_required
def sync_documents():
    """Synchronize investment documents between systems - Phase 3: Database Integration"""
    try:
        response = requests.get(
            f"{INVESTDOCS_INTERNAL_URL}/api/documents",
            headers={
                'Authorization': f'Bearer {create_sso_token(current_user)}',
                'X-User-Id': str(current_user.id)
            },
            timeout=10
        )

        if response.status_code == 200:
            documents = response.json()
            logger.info(f"Synced {len(documents)} documents for user {current_user.id}")
            return jsonify({
                'success': True,
                'documents_synced': len(documents),
                'last_sync': str(__import__('datetime').datetime.now())
            }), 200
        else:
            return jsonify({'error': 'Failed to sync documents'}), response.status_code

    except Exception as e:
        logger.error(f"Document sync error: {str(e)}")
        return jsonify({'error': 'Sync failed', 'details': str(e)}), 500


# ===========================
# PHASE 3: DOCUMENT STORAGE
# ===========================

@investdocs_bp.route('/documents', methods=['GET'])
@login_required
def get_documents():
    """Get user's investment documents - Phase 3: Database Integration"""
    try:
        response = requests.get(
            f"{INVESTDOCS_INTERNAL_URL}/api/documents",
            headers={
                'Authorization': f'Bearer {create_sso_token(current_user)}',
                'X-User-Id': str(current_user.id)
            },
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Get documents error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve documents'}), 500


@investdocs_bp.route('/documents/<doc_id>', methods=['GET', 'DELETE'])
@login_required
def document_detail(doc_id):
    """Get or delete specific document - Phase 3: Database Integration"""
    try:
        response = requests.request(
            method=request.method,
            url=f"{INVESTDOCS_INTERNAL_URL}/api/documents/{doc_id}",
            headers={
                'Authorization': f'Bearer {create_sso_token(current_user)}',
                'X-User-Id': str(current_user.id)
            },
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Document detail error: {str(e)}")
        return jsonify({'error': 'Failed to process document'}), 500


# ===========================
# PHASE 4: FEATURE INTEGRATION
# ===========================

@investdocs_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Get user's InvestDocs statistics - Phase 4: Feature Integration"""
    try:
        response = requests.get(
            f"{INVESTDOCS_INTERNAL_URL}/api/stats",
            headers={
                'Authorization': f'Bearer {create_sso_token(current_user)}',
                'X-User-Id': str(current_user.id)
            },
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve stats'}), 500


@investdocs_bp.route('/integration-status', methods=['GET'])
def integration_status():
    """Get integration status information - Useful for monitoring and debugging"""
    try:
        try:
            response = requests.get(
                f"{INVESTDOCS_INTERNAL_URL}/health",
                timeout=5
            )
            investdocs_healthy = response.status_code == 200
        except:
            investdocs_healthy = False

        return jsonify({
            'status': 'ok',
            'mode': INVESTDOCS_MODE,
            'investdocs_url': INVESTDOCS_STANDALONE_URL,
            'investdocs_healthy': investdocs_healthy,
            'proxy_enabled': INVESTDOCS_PROXY_API,
            'phases': {
                'phase1': {'name': 'Iframe Embedding', 'status': 'enabled'},
                'phase2': {'name': 'SSO Integration', 'status': 'enabled' if create_sso_token else 'disabled'},
                'phase3': {'name': 'Database Integration', 'status': 'enabled'},
                'phase4': {'name': 'Feature Integration', 'status': 'enabled'},
            }
        }), 200
    except Exception as e:
        logger.error(f"Integration status error: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ===========================
# ERROR HANDLERS
# ===========================

@investdocs_bp.errorhandler(403)
def forbidden(error):
    """Handle permission denied errors"""
    return jsonify({'error': 'Access denied'}), 403


@investdocs_bp.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return jsonify({'error': 'Resource not found'}), 404


@investdocs_bp.errorhandler(500)
def server_error(error):
    """Handle server errors"""
    logger.error(f"InvestDocs route error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


# Logging
logger.info(f"InvestDocs integration initialized in {INVESTDOCS_MODE} mode")
logger.info(f"Standalone URL: {INVESTDOCS_STANDALONE_URL}")
logger.info(f"Proxy API enabled: {INVESTDOCS_PROXY_API}")
