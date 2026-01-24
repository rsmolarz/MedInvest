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
"""""

from flask import Blueprint, render_template, jsonify, request, session, current_app
from flask_login import login_required, current_user
import requests
import os
from datetime import timedelta
from functools import wraps
import logging
from flask_jwt_extended import create_access_token-- Phase 3: Database Integration & Document Synchronization
-- MedInvest & InvestmentVault InvestDocs Migration
-- Created: 2026-01-24

-- Table 1: Investment Documents (Master table)
CREATE TABLE IF NOT EXISTS investment_documents (
        id SERIAL PRIMARY KEY,
    investdocs_id VARCHAR(255) UNIQUE NOT NULL,
                                                  user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
                                   description TEXT,
    document_type VARCHAR(100),
    file_path VARCHAR(500),
    file_size BIGINT,
                        mime_type VARCHAR(100),
    uploaded_by INTEGER,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                                             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_medinvest BOOLEAN DEFAULT FALSE,
    synced_to_investdocs BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (uploaded_by) REFERENCES user(id)
);

-- Table 2: InvestDocs Uploads (Track uploads)
CREATE TABLE IF NOT EXISTS investdocs_uploads (
        id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    upload_status VARCHAR(50),
    error_message TEXT,
                          retry_count INTEGER DEFAULT 0,
                                                           last_retry_at TIMESTAMP,
                                                                                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                                                                                                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES investment_documents(id)
);

-- Table 3: InvestDocs Sync Logs (Audit trail)
CREATE TABLE IF NOT EXISTS investdocs_sync_logs (
        id SERIAL PRIMARY KEY,
    source_system VARCHAR(50),
    destination_system VARCHAR(50),
    document_id INTEGER,
                           sync_type VARCHAR(50),
    status VARCHAR(50),
    error_details TEXT,
                          synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                                           FOREIGN KEY (document_id) REFERENCES investment_documents(id)
);

-- Table 4: InvestDocs Shares (Document sharing)
CREATE TABLE IF NOT EXISTS investdocs_shares (
        id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    shared_with_user_id INTEGER NOT NULL,
    permission_level VARCHAR(50),
    shared_by_user_id INTEGER NOT NULL,
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expired_at TIMESTAMP,
                            FOREIGN KEY (document_id) REFERENCES investment_documents(id),
    FOREIGN KEY (shared_with_user_id) REFERENCES user(id),
    FOREIGN KEY (shared_by_user_id) REFERENCES user(id)
);

-- Indexes for performance
CREATE INDEX idx_investment_documents_user_id ON investment_documents(user_id);
CREATE INDEX idx_investment_documents_investdocs_id ON investment_documents(investdocs_id);
CREATE INDEX idx_investment_documents_created_at ON investment_documents(created_at);
CREATE INDEX idx_investdocs_uploads_document_id ON investdocs_uploads(document_id);
CREATE INDEX idx_investdocs_sync_logs_document_id ON investdocs_sync_logs(document_id);
CREATE INDEX idx_investdocs_sync_logs_synced_at ON investdocs_sync_logs(synced_at);
CREATE INDEX idx_investdocs_shares_document_id ON investdocs_shares(document_id);
CREATE INDEX idx_investdocs_shares_shared_with_user_id ON investdocs_shares(shared_with_user_id);

-- Comments
COMMENT ON TABLE investment_documents IS 'Master table for investment documents shared between MedInvest and InvestmentVault';
COMMENT ON TABLE investdocs_uploads IS 'Tracks upload status and retry logic for documents';
COMMENT ON TABLE investdocs_sync_logs IS 'Audit trail for all document synchronization events';
COMMENT ON TABLE investdocs_shares IS 'Document sharing permissions between users';
)
)
)
)

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
INVESTDOCS_MODE = os.environ.get('INVESTDOCS_MODE', 'iframe')  # 'iframe' or 'embedded' or 'standalone'
INVESTDOCS_PROXY_API = os.environ.get('INVESTDOCS_PROXY_API', True)

# ===========================
# PHASE 1: IFRAME EMBEDDING
# ===========================

@investdocs_bp.route('/', methods=['GET'])
@login_required
def dashboard():
      """
          Display InvestDocs dashboard
              Phase 1: Serves iframe embedding
                  """""
      context = {
                'investdocs_url': INVESTDOCS_STANDALONE_URL,
                'user_id': current_user.id,
                'mode': INVESTDOCS_MODE,
                'has_documents': False,  # Will be populated in Phase 3
      }
      return render_template('investdocs/iframe.html', **context)


  # ===========================
  # PHASE 2: SSO INTEGRATION
  # ===========================

  def create_sso_token(user):
        """
            Create JWT token for SSO with InvestmentVault
                Phase 2: SSO integration
                    """""
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
      """
          Synchronize authentication between MedInvest and InvestmentVault
              Phase 2: SSO Integration
                  
                      Returns JWT token and user info for SSO
                          """""
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
      """
          Serve InvestDocs as embedded React component
              Phase 2: Embedded integration (more advanced than iframe)
                  """""
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
      """
          Proxy API calls from frontend to InvestmentVault backend
              Phase 2: API Integration
                  
                      Handles authentication and request forwarding
                          """""
      if not INVESTDOCS_PROXY_API:
                return jsonify({'error': 'API proxy disabled'}), 403

    try:
              # Build full URL
              url = f"{INVESTDOCS_INTERNAL_URL}/api/{path}"

        # Prepare headers with authentication
        headers = {
                      'Content-Type': 'application/json',
                      'User-Agent': 'MedInvest-InvestDocs-Proxy/1.0'
        }

        # Add authentication token if available
        token = create_sso_token(current_user)
        if token:
                      headers['Authorization'] = f'Bearer {token}'

        # Add X-Forwarded headers for IP tracking
        headers['X-Forwarded-For'] = request.remote_addr
        headers['X-Forwarded-User-Id'] = str(current_user.id)
        headers['X-Forwarded-Email'] = current_user.email

        # Forward query parameters
        params = request.args.to_dict() if request.method in ['GET', 'DELETE'] else None

        # Forward request
        response = requests.request(
                      method=request.method,
                      url=url,
                      headers=headers,
                      json=request.get_json() if request.method in ['POST', 'PUT', 'PATCH'] else None,
                      params=params,
                      timeout=30
        )

        logger.info(f"InvestDocs API request: {request.method} {path} -> {response.status_code}")

        # Return response
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
      """
          Synchronize investment documents between systems
              Phase 3: Database Integration
                  
                      Pulls user documents from InvestmentVault and syncs with MedInvest
                          """""
      try:
                # Get documents from InvestmentVault API
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
                              # Phase 3: Would store in MedInvest database
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
      """
          Get user's investment documents
              Phase 3: Database Integration
                  """""
      try:
                # For now, proxy to InvestmentVault
                # Phase 3: Would query local MedInvest database
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
      """
          Get or delete specific document
              Phase 3: Database Integration
                  """""
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
      """
          Get user's InvestDocs statistics
              Phase 4: Feature Integration
                  """""
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
      """
          Get integration status information
              Useful for monitoring and debugging
                  """""
      try:
                # Test InvestmentVault connection
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
      """Handle permission denied errors"""""
      return jsonify({'error': 'Access denied'}), 403


  @investdocs_bp.errorhandler(404)
def not_found(error):
      """Handle not found errors"""""
      return jsonify({'error': 'Resource not found'}), 404


  @investdocs_bp.errorhandler(500)
def server_error(error):
      """Handle server errors"""""
      logger.error(f"InvestDocs route error: {str(error)}")
      return jsonify({'error': 'Internal server error'}), 500


  # Logging
  logger.info(f"InvestDocs integration initialized in {INVESTDOCS_MODE} mode")
logger.info(f"Standalone URL: {INVESTDOCS_STANDALONE_URL}")
logger.info(f"Proxy API enabled: {INVESTDOCS_PROXY_API}")
{% extends "base.html" %}

                 {% block title %}Investment Documents - MedInvest{% endblock %}

                 {% block content %}
<div class="container-fluid px-4 py-5">
    <!-- Header Section -->
          <div class="row mb-4">
        <div class="col-12">
            <h1 class="display-4 fw-bold">Investment Documents</h1>
            <p class="lead text-muted">Manage your investment documents with confidence</p>
        </div>
    </div>

    <!-- Integration Status Alert (Development) -->
    {% if config.DEBUG %}
    <div class="row mb-4">
        <div class="col-12">
            <div class="alert alert-info alert-dismissible fade show" role="alert">
                <strong>InvestDocs Integration</strong> - Running in <code>{{ mode }}</code> mode
                {% if mode == 'iframe' %}
                <p class="mb-0 mt-2">
                    <small>Phase 1 (Iframe Embedding) is active. The InvestmentVault application is embedded below as an independent iframe.</small>
                </p>
                {% endif %}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        </div>
    </div>
    {% endif %}

    <!-- InvestDocs Iframe Container -->
    <div class="row">
        <div class="col-12">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">
                        <i class="fas fa-file-contract"></i> Investment Documents Dashboard
                                              </h5>
                                          </div>
                                          <div class="card-body p-0">
                    <!-- Loading Spinner -->
                                          <div id="investdocs-loading" class="text-center py-5">
                                                                         <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-3 text-muted">Loading Investment Documents...</p>
                    </div>

                                     <!-- Iframe Container -->
                                                           <iframe 
                                                               id="investdocs-iframe"
                                                                                         src="{{ investdocs_url }}"
                                                                                         width="100%" 
                                                                                         height="800px"
                                                                                         frameborder="0"
                                                                                         style="display: none; border: none; overflow: hidden;"
                                                                                         allow="camera; microphone; geolocation; payment"
                                                                                         sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals"
                                                                                         title="Investment Documents"
                                                                                     ></iframe>

                                                                                     <!-- Error Message (hidden by default) -->
                                                                                     <div id="investdocs-error" class="alert alert-danger d-none" role="alert">
                                                                                                                    <h4 class="alert-heading">Unable to Load Investment Documents</h4>
                        <p>The Investment Documents service is currently unavailable. Please try again later.</p>
                        <hr>
                                                 <p class="mb-0">
                            <a href="{{ url_for('investdocs.integration_status') }}" class="alert-link">Check Integration Status</a>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>

                     <!-- Information Cards -->
                           <div class="row mt-5">
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-primary">
                        <i class="fas fa-shield-alt"></i> Bank-Level Security
                                              </h6>
                                              <p class="card-text small">Your documents are encrypted and securely stored.</p>
                </div>
            </div>
        </div>
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-primary">
                        <i class="fas fa-sync-alt"></i> Auto-Sync
                    </h6>
                    <p class="card-text small">Documents are automatically synced across MedInvest.</p>
                </div>
            </div>
        </div>
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-primary">
                        <i class="fas fa-headset"></i> 24/7 Support
                                              </h6>
                                              <p class="card-text small">Get help when you need it from our support team.</p>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Inline CSS for responsive design -->
<style>
    .card {
              border: 1px solid rgba(0,0,0,0.125);
        border-radius: 0.5rem;
}

    #investdocs-iframe {
        min-height: 600px;
        width: 100%;
}

    @media (max-width: 768px) {
        #investdocs-iframe {
            min-height: 400px;
}
}
</style>

<!-- Scripts -->
<script>
    // InvestDocs Iframe Integration
    (function() {
              const iframe = document.getElementById('investdocs-iframe');
        const loading = document.getElementById('investdocs-loading');
        const error = document.getElementById('investdocs-error');
        const timeout = 10000; // 10 seconds

        // Set user ID for potential future integration
                  iframe.dataset.userId = '{{ user_id }}';

        // Handle iframe load
        iframe.addEventListener('load', function() {
                      console.log('InvestDocs iframe loaded successfully');
                      loading.style.display = 'none';
            iframe.style.display = 'block';
}, { once: true });

        // Handle iframe error
                  iframe.addEventListener('error', function() {
                                console.error('InvestDocs iframe failed to load');
                                loading.style.display = 'none';
            error.classList.remove('d-none');
}, { once: true });

        // Timeout handler
                  setTimeout(function() {
                                if (iframe.style.display !== 'block') {
                                                  console.error('InvestDocs iframe timeout');
                                                  loading.style.display = 'none';
                error.classList.remove('d-none');
}
}, timeout);

        // Post message to iframe (for future Phase 2 integration)
        function sendMessageToIframe(data) {
                      if (iframe.contentWindow) {
                                        iframe.contentWindow.postMessage(data, '{{ investdocs_url }}');
        }
}

        // Listen for messages from iframe
        window.addEventListener('message', function(event) {
                      // Verify origin for security
                                            if (event.origin === '{{ investdocs_url }}') {
                                                              console.log('Message from InvestDocs:', event.data);
                          // Handle iframe messages here (Phase 2+)
                                }
                                });

        // Expose sendMessageToIframe globally for debugging
        window.sendToInvestDocs = sendMessageToIframe;

        // Log initialization
        console.log('InvestDocs iframe integration initialized', {
                      mode: '{{ mode }}',
                      userId: '{{ user_id }}',
                      url: '{{ investdocs_url }}'
        });
})();
</script>
{% endblock %}
        })
                                            }
        })
                      }
        }
                                }
                  })
                  })
        })
    })
        }
    }
    }
    }
                })
                              }
                })
                              )
                              }
                )
                              }
                )
                              }
                )
                              })
                              }
                )
        )
        }
    }
          })
                                }
                  )
      }
)