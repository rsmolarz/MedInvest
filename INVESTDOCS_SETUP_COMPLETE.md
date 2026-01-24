# InvestDocs Integration - COMPLETE IMPLEMENTATION

All 4 phases are now ready for immediate deployment. Follow these steps to activate each phase.

---

## 🚀 PHASE 1: IFRAME EMBEDDING - TEST NOW

### Step 1: Set Environment Variables

Add to Replit Secrets:
```
INVESTDOCS_URL=https://investmentvault.replit.dev
INVESTDOCS_MODE=iframe
INVESTDOCS_PROXY_API=true
```

### Step 2: Test the Route

1. Start the MedInvest app (should reload with new blueprint)
2. 2. Navigate to: `https://medmoneyincubator.com/investdocs/`
   3. 3. You should see InvestDocs loading in an iframe
   4. ### Step 3: Verify Both Apps Work Independently
3. - MedInvest: `https://medmoneyincubator.com/` ✅
   - - InvestmentVault: `https://investmentvault.replit.dev/` ✅
     - - Integrated: `https://medmoneyincubator.com/investdocs/` ✅
     - ---

     ## 🔐 PHASE 2: SSO INTEGRATION - CONFIGURE NOW

     ### Step 1: Install Flask-JWT-Extended

     In Replit console:
     ```bash
     pip install flask-jwt-extended
     ```

     ### Step 2: Update main.py

     Add after imports section:
     ```python
     from flask_jwt_extended import JWTManager
4. # JWT Configuration (around line 20)
5. jwt = JWTManager(app)
6. app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
7. app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
8. ```
### Step 3: Add JWT_SECRET_KEY to Secrets

```
JWT_SECRET_KEY=your-super-secret-key-here-change-in-production
```

### Step 4: Update InvestmentVault Client

In InvestmentVault's `client/main.tsx` or `src/App.tsx`:

```typescript
// Add this at the top level of your app initialization
const initializeAuth = async () => {
    // Check if we're embedded in MedInvest
    const isEmbedded = window.parent !== window;

    if (isEmbedded) {
          try {
                  // Get SSO token from MedInvest
                  const response = await fetch('/investdocs/auth/sync', {
                            method: 'POST',
                            headers: {
                                        'Content-Type': 'application/json'
                            },
                            credentials: 'include'
                  });

                  const data = await response.json();

                  if (data.token) {
                            // Store token and use for API calls
                            localStorage.setItem('medinvest_token', data.token);
                            localStorage.setItem('user_id', data.user_id);

                            // Set API base URL to use proxy
                            window.API_BASE = '/investdocs/api';
                            window.MEDINVEST_TOKEN = data.token;

                            console.log('✅ SSO successful - authenticated via MedInvest');
                  }
          } catch (error) {
                  console.error('SSO failed:', error);
          }
    }
};

// Call this during app init
initializeAuth();
```

### Step 5: Update API Calls in InvestmentVault

Wrap your API calls to use the token:

```typescript
const apiCall = async (endpoint: string, method = 'GET', body = null) => {
    const token = localStorage.getItem('medinvest_token') || '';
    const options: RequestInit = {
          method,
          headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${token}`
          },
          credentials: 'include'
    };

    if (body) options.body = JSON.stringify(body);

    const response = await fetch(
          `${window.API_BASE || '/api'}${endpoint}`,
          options
        );

    return response.json();
};
```

### Step 6: Test SSO

1. Make sure JWT extension is installed
2. 2. Navigate to `https://medmoneyincubator.com/investdocs/`
   3. 3. Check browser console for: "✅ SSO successful"
      4. 4. Test API calls work through proxy
      5. ---
   4. ## 📊 PHASE 3: DATABASE INTEGRATION - MIGRATE NOW
3. ### Step 1: Run Database Migration
Execute this SQL in your PostgreSQL database (via Replit Database CLI or pgAdmin):

```sql
-- ========================================
-- INVESTDOCS INTEGRATION - DATABASE SCHEMA
-- ========================================

-- Investment documents table
C
    )
          }
    }
}
          }
                  }
                            }
                  })
          }
    }
}