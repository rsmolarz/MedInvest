# InvestDocs Integration Guide - MedInvest

Complete roadmap for integrating InvestmentVault (InvestDocs) into MedInvest with support for both standalone and embedded modes.

## Table of Contents
1. [Overview](#overview)
2. 2. [Phase 1: Iframe Embedding](#phase-1-iframe-embedding)
   3. 3. [Phase 2: SSO Integration](#phase-2-sso-integration)
      4. 4. [Phase 3: Database Integration](#phase-3-database-integration)
         5. 5. [Phase 4: Feature Integration](#phase-4-feature-integration)
            6. 6. [Deployment](#deployment)
               7. 7. [Troubleshooting](#troubleshooting)
               8. ---
            7. ## Overview
         6. This integration allows InvestmentVault to run as both:
         7. - **Standalone**: Independent application at its own URL
            - - **Integrated**: Embedded feature within MedInvest
            - The integration is implemented in phases, allowing gradual enhancement without breaking existing functionality.
         8. ### Files Created
      5. ```
      6. MedInvest/
      7. ├── routes/investdocs.py                    # Integration routes
      8. ├── templates/investdocs/
      9. │   ├── iframe.html                         # Phase 1: Iframe template
      10. │   ├── embedded.html                       # Phase 2: Embedded template
      11. │   └── widgets/                            # Phase 4: Components
      12. ├── static/investdocs/                      # React build output (Phase 2+)
      13. └── INVESTDOCS_INTEGRATION_GUIDE.md         # This file
      14. ```
   4. ---
3. ## Phase 1: Iframe Embedding
**Status**: ✅ IMPLEMENTED  
**Effort**: 1-2 hours  
**Risk**: Minimal

### What It Does
Embeds InvestmentVault as an independent iframe on a new MedInvest page at `/investdocs/`.

### Benefits
- Zero code changes needed in either application
- - Completely independent operation
  - - Both apps can run standalone
    - - Easy rollback (remove 1 iframe)
      - - Users stay logged into MedInvest
      - ### Implementation Steps
    - #### 1. Register Blueprint in main.py
  - ```python
  - from routes.investdocs import investdocs_bp
- app.register_blueprint(investdocs_bp)
- ```
#### 2. Set Environment Variables

```bash
# In .replit or environment
INVESTDOCS_URL=https://investmentvault.replit.dev
INVESTDOCS_MODE=iframe
```

#### 3. Add Menu Item

Add to navigation/sidebar:
```html
<li>
      <a href="{{ url_for('investdocs.dashboard') }}">
                <i class="fas fa-file-contract"></i> Investment Documents
      </a>
</li>li>
```

#### 4. Test

Navigate to `https://medmoneyincubator.com/investdocs/` and InvestDocs should load in the iframe.

### Limitations
- Cannot easily share data between apps
- - Separate logins required
  - - No unified navigation
    -
    - ### Next Steps
    - When ready, upgrade to Phase 2 for SSO integration.
    -
    - ---
    -
    - ## Phase 2: SSO Integration
    -
    - **Status**: ⚠️ READY
    - **Effort**: 3-4 hours
    - **Risk**: Low-Medium
    -
    - ### What It Does
    - Adds single sign-on so users logged into MedInvest are automatically authenticated in InvestDocs.
    -
    - ### Benefits
    - - Seamless user experience
      - - Shared authentication
        - - API proxy for data access
          - - Better integration
            -
            - ### Prerequisites
            - - Phase 1 (Iframe) working
              - - Flask-JWT-Extended installed: `pip install flask-jwt-extended`
                - - InvestmentVault updated to accept JWT tokens
                  -
                  - ### Implementation Steps
                  -
                  - #### 1. Install JWT Extension
                  -
                  - ```bash
                  - pip install flask-jwt-extended
                  - ```
                  -
                  - #### 2. Configure JWT in main.py
                  -
                  - ```python
                  - from flask_jwt_extended import JWTManager
                  -
                  - jwt = JWTManager(app)
                  - app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
                  - ```
                  -
                  - #### 3. Enable SSO Routes
                  -
                  - The `/auth/sync` endpoint is already in investdocs.py. Update InvestmentVault to:
                  - - Accept Authorization header with JWT token
                    - - Validate token against MedInvest's JWT secret
                      -
                      - #### 4. Update InvestDocs Frontend
                      -
                      - In InvestmentVault's client:
                      -
                      - ```typescript
                      - // Detect if embedded in MedInvest
                      - const isEmbedded = window.parent !== window;
                      -
                      - if (isEmbedded) {
                      -   // Get token from MedInvest
                      -     const token = await fetch('/investdocs/auth/sync', {
                      -     method: 'POST'
                      -   }).then(r => r.json()).then(d => d.token);
                      -
                      -   // Use token for API calls
                      -     setAuthToken(token);
                      - }
                      - ```
                      -
                      - #### 5. Configure API Proxy
                      -
                      - Update InvestDocs to use `/investdocs/api/` when embedded:
                      -
                      - ```typescript
                      - const API_BASE = isEmbedded ? '/investdocs/api' : '/api';
                      - ```
                      -
                      - ### Testing Checklist
                      -
                      - - [ ] User logged into MedInvest can access /investdocs
                        - [ ] - [ ] Token is successfully synced
                        - [ ] - [ ] API calls work through proxy
                        - [ ] - [ ] Documents load correctly
                        - [ ] - [ ] Logout clears InvestDocs session
                        - [ ]
                        - [ ] ---
                        - [ ]
                        - [ ] ## Phase 3: Database Integration
                        - [ ]
                        - [ ] **Status**: ⚠️ READY
                        - [ ] **Effort**: 4-6 hours
                        - [ ] **Risk**: Medium
                        - [ ]
                        - [ ] ### What It Does
                        - [ ] Syncs user documents between MedInvest and InvestmentVault databases.
                        - [ ]
                        - [ ] ### Schema Changes
                        - [ ]
                        - [ ] Add tables to MedInvest database:
                        - [ ]
                        - [ ] ```sql
                        - [ ] -- Investment documents
                        - [ ] CREATE TABLE investment_documents (
                        - [ ]     id SERIAL PRIMARY KEY,
                        - [ ]     user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        - [ ]     document_type VARCHAR(50),
                        - [ ]     file_path VARCHAR(255),
                        - [ ]     file_size INTEGER,
                        - [ ]     upload_source VARCHAR(20), -- 'investdocs' or 'medinvest'
                        - [ ]     metadata JSONB,
                        - [ ]     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        - [ ]     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        - [ ] );
                        - [ ]
                        - [ ] -- Document uploads
                        - [ ] CREATE TABLE investdocs_uploads (
                        - [ ]     id SERIAL PRIMARY KEY,
                        - [ ]     user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        - [ ]     document_id INTEGER REFERENCES investment_documents(id) ON DELETE CASCADE,
                        - [ ]     filename VARCHAR(255),
                        - [ ]     content_type VARCHAR(100),
                        - [ ]     file_size INTEGER,
                        - [ ]     uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        - [ ]     synced_to_investdocs BOOLEAN DEFAULT FALSE,
                        - [ ]     synced_at TIMESTAMP
                        - [ ] );
                        - [ ]
                        - [ ] -- Sync logs
                        - [ ] CREATE TABLE investdocs_sync_logs (
                        - [ ]     id SERIAL PRIMARY KEY,
                        - [ ]     user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        - [ ]     sync_type VARCHAR(20), -- 'upload', 'download', 'delete'
                        - [ ]     document_id INTEGER,
                        - [ ]     status VARCHAR(20), -- 'pending', 'success', 'failed'
                        - [ ]     error_message TEXT,
                        - [ ]     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        - [ ] );
                        - [ ] ```
                        - [ ]
                        - [ ] ### Implementation
                        - [ ]
                        - [ ] Routes are ready in investdocs.py:
                        - [ ] - `POST /investdocs/sync/documents` - Trigger sync
                        - [ ] - `GET /investdocs/documents` - Get user's documents
                        - [ ] - `GET /investdocs/documents/<id>` - Get specific document
                        - [ ]
                        - [ ] ### Sync Logic
                        - [ ]
                        - [ ] ```python
                        - [ ] # In routes/investdocs.py - sync_documents()
                        - [ ] # This endpoint:
                        - [ ] # 1. Fetches documents from InvestmentVault API
                        - [ ] # 2. Stores them in MedInvest database
                        - [ ] # 3. Tracks sync status
                        - [ ] # 4. Handles conflicts
                        - [ ] ```
                        - [ ]
                        - [ ] ### Testing
                        - [ ]
                        - [ ] ```bash
                        - [ ] # Test sync endpoint
                        - [ ] curl -X POST http://localhost:5000/investdocs/sync/documents \
                        - [ ]   -H "Authorization: Bearer {token}"
                        - [ ]
                        - [ ]   # Test document retrieval
                        - [ ]   curl http://localhost:5000/investdocs/documents \
                        - [ ]     -H "Authorization: Bearer {token}"
                        - [ ] ```
                        - [ ]
                        - [ ] ---
                        - [ ]
                        - [ ] ## Phase 4: Feature Integration
                        - [ ]
                        - [ ] **Status**: ⚠️ DESIGN READY
                        - [ ] **Effort**: 6-8 hours
                        - [ ] **Risk**: Medium-High
                        - [ ]
                        - [ ] ### What It Does
                        - [ ] Fully integrates InvestDocs features into MedInvest UI.
                        - [ ]
                        - [ ] ### Components to Integrate
                        - [ ]
                        - [ ] 1. **Document Widget** - Show recent documents on dashboard
                        - [ ] 2. **Portfolio Documents** - Link documents to portfolio entries
                        - [ ] 3. **Mentorship Documents** - Share documents with mentors
                        - [ ] 4. **Notifications** - Alert on document uploads/reviews
                        - [ ] 5. **Search** - Include documents in global search
                        - [ ]
                        - [ ] ### Implementation Example
                        - [ ]
                        - [ ] ```python
                        - [ ] # In routes/portfolio.py
                        - [ ] @portfolio_bp.route('/<int:portfolio_id>/documents')
                        - [ ] @login_required
                        - [ ] def portfolio_documents(portfolio_id):
                        - [ ]     """Show investment documents for this portfolio"""
                        - [ ]     # Fetch portfolio documents via investdocs API
                        - [ ]     documents = requests.get(
                        - [ ]         f'/investdocs/documents?portfolio_id={portfolio_id}',
                        - [ ]             headers=get_auth_headers()
                        - [ ]             ).json()
                        - [ ]             return render_template('portfolio/documents.html', documents=documents)
                        - [ ]         ```
                        - [ ]
                        - [ ] ### UI Components
                        - [ ]
                        - [ ] ```html
                        - [ ] <!-- Document widget for dashboard -->
                        - [ ] <div class="investment-documents-widget">
                            <h5>Recent Documents</h5>
                                <ul id="recent-documents"></ul>
                                    <script>
                                              fetch('/investdocs/documents?limit=5')
                                                  .then(r => r.json())
                                                  .then(docs => {
                                                                    // Render documents
                                                                });
                                    </script>
                                    </div>
                                    ```
                      - ---
                  - ## Deployment
                - ### Environment Variables
              - ```bash
              - # Phase 1
              - INVESTDOCS_URL=https://investmentvault-standalone.replit.dev
              - INVESTDOCS_MODE=iframe
              - INVESTDOCS_PROXY_API=true
            - # Phase 2
            - JWT_SECRET_KEY=your-secret-key
            - INVESTDOCS_INTERNAL_URL=http://investmentvault:3000  # Docker/internal
          - # Phase 3+
          - INVESTDOCS_SYNC_ENABLED=true
          - INVESTDOCS_SYNC_INTERVAL=3600  # Seconds
          - ```
        - ### Standalone Setup
      - InvestmentVault remains unchanged:
    - ```bash
    - cd InvestmentVault
    - npm install
    - npm run dev  # Runs on :3000
    - ```
  - ### Integrated Setup
- ```bash
- # Build InvestDocs for embedding (Phase 2+)
- cd InvestmentVault
- npm run build
- cp -r dist/* ../MedInvest/static/investdocs/
# Run MedInvest with InvestDocs
cd MedInvest
export INVESTDOCS_URL=http://localhost:3000
python main.py
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  medinvest:
      build: ./MedInvest
          ports:
                - "5000:5000"
                    environment:
                          - INVESTDOCS_URL=http://investmentval:3000
                                - INVESTDOCS_MODE=iframe
                                    depends_on:
                                          - investmentval

                                            investmentval:
                                                build: ./InvestmentVault
                                                    ports:
                                                          - "3000:3000"
                                                              environment:
                                                                    - NODE_ENV=production
                                                                    ```

                                                                    ---

                                                                    ## Troubleshooting

                                                                    ### Iframe Not Loading

                                                                    1. Check `INVESTDOCS_URL` environment variable
                                                                    2. Verify InvestmentVault is running
                                                                    3. Check browser console for CORS errors
                                                                    4. Ensure iframe sandbox allows the source

                                                                    ```javascript
                                                                    // In browser console
                                                                    console.log('InvestDocs URL:', document.getElementById('investdocs-iframe').src);
                                                                    ```

                                                                    ### SSO Token Issues

                                                                    ```bash
                                                                    # Check JWT is being created
                                                                    curl -X POST http://localhost:5000/investdocs/auth/sync \
                                                                      -H "Authorization: Bearer {user_token}" \
                                                                        -v
                                                                        ```

                                                                        ### Sync Failures

                                                                        Check logs:
                                                                        ```bash
                                                                        # View sync errors
                                                                        curl http://localhost:5000/investdocs/integration-status
                                                                        ```

                                                                        ### Cross-Origin Issues

                                                                        Ensure CORS is configured:

                                                                        ```python
                                                                        from flask_cors import CORS

                                                                        CORS(app, resources={
                                                                            r"/investdocs/*": {
                                                                                    "origins": ["https://investmentvault-domain.com"],
                                                                                            "methods": ["GET", "POST", "PUT", "DELETE"],
                                                                                                    "allow_headers": ["Authorization", "Content-Type"]
                                                                                                        }
                                                                                                        })
                                                                                                        ```
                                                                                                        
                                                                                                        ---
                                                                                                        
                                                                                                        ## Monitoring
                                                                                                        
                                                                                                        ### Health Checks
                                                                                                        
                                                                                                        ```bash
                                                                                                        # Check integration status
                                                                                                        curl http://localhost:5000/investdocs/integration-status
                                                                                                        
                                                                                                        # Response:
                                                                                                        {
                                                                                                          "status": "ok",
                                                                                                            "mode": "iframe",
                                                                                                              "investdocs_healthy": true,
                                                                                                                "phases": {
                                                                                                                    "phase1": {"status": "enabled"},
                                                                                                                        "phase2": {"status": "enabled"},
                                                                                                                            "phase3": {"status": "enabled"},
                                                                                                                                "phase4": {"status": "enabled"}
                                                                                                                                  }
                                                                                                                                  }
                                                                                                                                  ```
                                                                                                                                  
                                                                                                                                  ### Logging
                                                                                                                                  
                                                                                                                                  All integration activity is logged:
                                                                                                                                  
                                                                                                                                  ```python
                                                                                                                                  logger.info(f"InvestDocs API request: {method} {path} -> {status}")
                                                                                                                                  logger.error(f"InvestDocs proxy error: {error}")
                                                                                                                                  ```
                                                                                                                                  
                                                                                                                                  ---
                                                                                                                                  
                                                                                                                                  ## Rollback Plan
                                                                                                                                  
                                                                                                                                  ### Phase 1 (Iframe)
                                                                                                                                  Simply remove the route:
                                                                                                                                  ```python
                                                                                                                                  # Comment out in main.py
                                                                                                                                  # app.register_blueprint(investdocs_bp)
                                                                                                                                  ```
                                                                                                                                  
                                                                                                                                  ### Phase 2+ (SSO/Database)
                                                                                                                                  Keep a branch with Phase 1 code:
                                                                                                                                  ```bash
                                                                                                                                  git checkout phase-1-stable
                                                                                                                                  ```
                                                                                                                                  
                                                                                                                                  ---
                                                                                                                                  
                                                                                                                                  ## Next Steps
                                                                                                                                  
                                                                                                                                  1. **Week 1**: Implement Phase 1 (Iframe) and test standalone
                                                                                                                                  2. **Week 2**: Implement Phase 2 (SSO) and test authentication
                                                                                                                                  3. **Week 3**: Implement Phase 3 (Database) and test syncing
                                                                                                                                  4. **Week 4**: Implement Phase 4 (Features) and polish UX
                                                                                                                                  
                                                                                                                                  ---
                                                                                                                                  
                                                                                                                                  ## Support
                                                                                                                                  
                                                                                                                                  For issues or questions:
                                                                                                                                  - Check `/investdocs/integration-status` endpoint
                                                                                                                                  - Review logs in MedInvest console
                                                                                                                                  - Test InvestmentVault independently
                                                                                                                                  
                                                                                                                                  ---
                                                                                                                                  
                                                                                                                                  ## Version History
                                                                                                                                  
                                                                                                                                  - v1.0 - Initial integration framework (All 4 phases)
                                                                                                                                  - v0.1 - Phase 1 iframe embedding")
                                                                                                                }
                                                                                                        }
                                                                        })
                                                  })
                                    </script></i>
      </a>
</li>