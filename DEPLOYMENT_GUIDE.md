# MedInvest Deployment Guide

Complete guide for deploying and maintaining the MedInvest platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Deployment Steps](#deployment-steps)
5. [Health Checks](#health-checks)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services

- **Python 3.11+** - Runtime environment
- **PostgreSQL 14+** - Production database
- **Redis** (optional) - Session caching and background jobs

### Required Accounts

- **Stripe** - Payment processing
- **SendGrid** - Email delivery
- **YouTube Data API** - Video integration
- **Buzzsprout** - Podcast integration

---

## Environment Setup

### Required Environment Variables

```bash
# Core Application
SESSION_SECRET=<random-32-char-string>
DATABASE_URL=postgresql://user:pass@host:5432/medinvest

# Stripe Integration
# Managed via Replit Stripe connector

# Email (SendGrid)
SENDGRID_API_KEY=<your-sendgrid-key>

# YouTube Integration
YOUTUBE_API_KEY=<your-youtube-api-key>

# Podcast Integration
BUZZSPROUT_API_TOKEN=<your-buzzsprout-token>

# AI Integration (MIA)
MIA_API_KEY=<your-mia-api-key>

# Optional: Scheduler
SCHEDULER_ENABLED=true

# JWT for SSO
JWT_SECRET_KEY=<random-secure-string>
```

### Optional Environment Variables

```bash
# Social Login (OAuth)
GOOGLE_CLIENT_ID=<client-id>
GOOGLE_CLIENT_SECRET=<client-secret>
GITHUB_CLIENT_ID=<client-id>
GITHUB_CLIENT_SECRET=<client-secret>

# Two-Factor Authentication
TOTP_ISSUER=MedInvest

# Webhook Signing
STRIPE_WEBHOOK_SECRET=<webhook-secret>
```

---

## Database Configuration

### Initial Setup

The application automatically creates tables on startup:

```python
with app.app_context():
    db.create_all()
```

### Migrations

For schema changes, use Alembic:

```bash
# Generate migration
flask db migrate -m "Description of changes"

# Apply migration
flask db upgrade
```

### Backup Strategy

```bash
# Daily backup (add to cron)
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore from backup
psql $DATABASE_URL < backup_file.sql
```

---

## Deployment Steps

### 1. Pre-Deployment Checklist

- [ ] All environment variables configured
- [ ] Database connection verified
- [ ] Stripe webhook endpoint configured
- [ ] Email service tested
- [ ] Social login redirect URIs updated

### 2. Deploy on Replit

1. Click the **Publish** button in the Replit interface
2. Configure deployment settings:
   - Port: 5000
   - Health check: `/health`
   - Start command: `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`

### 3. Post-Deployment

1. Verify health check: `curl https://your-domain.replit.app/health`
2. Test critical flows:
   - User registration/login
   - Stripe checkout
   - Email delivery
3. Set up Stripe webhook:
   - Endpoint: `https://your-domain.replit.app/subscription/webhook`
   - Events: `customer.subscription.*`, `invoice.*`

---

## Health Checks

### Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Basic health check | `{"status": "healthy"}` |
| `/health/detailed` | Detailed status | Full system status |

### Health Check Implementation

```python
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health/detailed')
def detailed_health():
    checks = {
        'database': check_database(),
        'stripe': check_stripe(),
        'email': check_email_service(),
    }
    
    all_healthy = all(c['healthy'] for c in checks.values())
    
    return jsonify({
        'status': 'healthy' if all_healthy else 'degraded',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }), 200 if all_healthy else 503
```

### Automated Monitoring

Configure Replit's built-in health checks:

1. Go to Deployment settings
2. Set health check path: `/health`
3. Set interval: 30 seconds
4. Set timeout: 10 seconds

---

## Monitoring

### Logging

Application logs are available in the Replit console. Log levels:

```python
# In production
logging.basicConfig(level=logging.INFO)

# For debugging
logging.basicConfig(level=logging.DEBUG)
```

### Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Response time | Health check | > 2s |
| Error rate | Logs | > 1% |
| Database connections | PostgreSQL | > 80% pool |
| Stripe webhook failures | Stripe dashboard | Any failure |

### Log Analysis

```bash
# View recent errors
grep -i error /tmp/logs/*.log

# Count requests by endpoint
grep "GET\|POST" /tmp/logs/access.log | awk '{print $7}' | sort | uniq -c | sort -rn
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptom:** `psycopg2.OperationalError: connection refused`

**Solution:**
```python
# Verify DATABASE_URL
import os
print(os.environ.get('DATABASE_URL'))

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

#### 2. Stripe Webhooks Failing

**Symptom:** Subscriptions not updating

**Solution:**
1. Check Stripe dashboard for webhook logs
2. Verify webhook secret matches
3. Ensure endpoint is publicly accessible

#### 3. Email Not Sending

**Symptom:** Users not receiving emails

**Solution:**
```python
# Test SendGrid connection
from utils.mailer import send_email
result = send_email("test@example.com", "Test", "<p>Test</p>")
print(result)
```

#### 4. 2FA Not Working

**Symptom:** TOTP codes rejected

**Solution:**
- Check server time is synced (NTP)
- Verify TOTP secret is stored correctly
- Use `valid_window=1` for clock drift tolerance

#### 5. Session Issues

**Symptom:** Users logged out unexpectedly

**Solution:**
```python
# Ensure SESSION_SECRET is set and consistent
app.secret_key = os.environ.get("SESSION_SECRET")

# Make sessions permanent
@app.before_request
def make_session_permanent():
    session.permanent = True
```

### Debug Mode

For development debugging:

```python
# Enable debug mode (NEVER in production)
app.debug = True
app.config['DEBUG'] = True
```

### Performance Issues

1. **Slow database queries:**
   - Add indexes to frequently queried columns
   - Use pagination for large result sets

2. **High memory usage:**
   - Check for memory leaks in background jobs
   - Limit concurrent connections

3. **Slow page loads:**
   - Enable caching for static assets
   - Optimize database queries
   - Use CDN for static files

---

## Rollback Procedure

If deployment fails:

1. **Use Replit Checkpoints:**
   - Go to Version Control
   - Select previous working checkpoint
   - Restore

2. **Database Rollback:**
   ```bash
   flask db downgrade
   ```

3. **Manual Rollback:**
   ```bash
   git revert HEAD
   git push
   ```

---

## Security Checklist

- [ ] SESSION_SECRET is random and secure
- [ ] Database credentials are not exposed
- [ ] HTTPS is enforced
- [ ] Rate limiting is enabled
- [ ] Input validation on all forms
- [ ] CSRF protection enabled
- [ ] SQL injection prevented (use ORM)
- [ ] XSS prevention (escape output)
- [ ] Sensitive data encrypted at rest
- [ ] Audit logging enabled

---

## Support

For issues with deployment:

1. Check Replit documentation
2. Review application logs
3. Contact Replit support for infrastructure issues

---

## Changelog

### v2.0.0
- Added Stripe subscription integration
- Enhanced notification system
- Added achievements/badges
- Implemented 2FA
- Added webhook system
- Advanced roles/permissions

### v1.0.0
- Initial release
