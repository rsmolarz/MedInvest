# MedInvest API Documentation

Complete API reference for the MedInvest platform - a social media platform for medical professionals to learn investment strategies.

## Base URL

```
Development: http://localhost:5000
Production: https://your-domain.replit.app
```

## Authentication

MedInvest uses session-based authentication for web routes and JWT tokens for API endpoints.

### Session Authentication
Most web routes require login via Flask-Login. Unauthenticated requests redirect to `/auth/login`.

### JWT Authentication
API endpoints accept Bearer tokens in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

---

## Stripe Payment & Subscription API

### GET /subscription/pricing
Display subscription pricing page with tier options.

**Response:** HTML page with Free, Pro ($29/mo), and Elite ($99/mo) tiers.

---

### POST /subscription/checkout
Create a Stripe checkout session for subscription.

**Request Body:**
```json
{
  "tier": "pro",
  "interval": "month"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tier | string | Yes | Subscription tier: "pro" or "elite" |
| interval | string | Yes | Billing interval: "month" or "year" |

**Response (Success):**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/..."
}
```

**Response (Error):**
```json
{
  "error": "Stripe not configured"
}
```

---

### GET /subscription/success
Handle successful Stripe checkout callback.

**Query Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Stripe checkout session ID |

**Response:** Redirects to subscription management page with success flash message.

---

### GET /subscription/manage
Display subscription management page.

**Response:** HTML page showing current subscription status, billing details, and upgrade options.

---

### GET /subscription/portal
Redirect to Stripe customer billing portal.

**Response:** 302 redirect to Stripe billing portal URL.

---

### POST /subscription/cancel
Cancel current subscription.

**Response (Success):**
```json
{
  "success": true,
  "message": "Subscription cancelled"
}
```

---

### POST /subscription/webhook
Handle Stripe webhook events.

**Headers:**
```
Stripe-Signature: <webhook_signature>
Content-Type: application/json
```

**Supported Events:**
- `customer.subscription.updated` - Subscription status changes
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.payment_succeeded` - Payment completed
- `invoice.payment_failed` - Payment failed

**Response:**
```json
{
  "status": "success"
}
```

---

## Notification API

### GET /notifications
List user notifications.

**Query Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| unread_only | bool | false | Filter to unread only |

**Response:** HTML page with notification list.

---

### GET /notifications/api/list
Get notifications as JSON.

**Response:**
```json
{
  "notifications": [
    {
      "id": 1,
      "type": "like",
      "title": "New Like",
      "message": "John liked your post",
      "is_read": false,
      "created_at": "2024-01-15T10:30:00Z",
      "url": "/posts/123"
    }
  ],
  "unread_count": 5
}
```

---

### POST /notifications/read/<id>
Mark notification as read.

**Response:**
```json
{
  "success": true
}
```

---

### POST /notifications/read-all
Mark all notifications as read.

**Response:**
```json
{
  "success": true
}
```

---

### GET /notifications/preferences
Display notification preferences page.

**Response:** HTML form with notification settings.

---

### POST /notifications/preferences
Update notification preferences.

**Request Body (form data):**
```
in_app_likes: on
in_app_comments: on
in_app_follows: on
in_app_mentions: on
in_app_deals: on
in_app_amas: on
in_app_messages: on
email_digest: daily
email_deals: on
email_amas: on
push_enabled: on
```

**Response:** Redirect to preferences page with success message.

---

## Analytics API

### GET /dashboard
User dashboard with personal analytics.

**Response:** HTML page containing:
- Post count, follower count, following count
- Total likes received
- Engagement rate percentage
- Recent activity feed
- Achievements display
- Deals explored count
- Courses enrolled count

---

### GET /admin/analytics
Admin analytics dashboard (admin only).

**Response:** HTML page with platform metrics:
```json
{
  "stats": {
    "total_users": 1500,
    "premium_users": 120,
    "pro_users": 100,
    "elite_users": 20,
    "dau": 450,
    "wau": 890,
    "dau_rate": 30.0,
    "premium_rate": 8.0,
    "monthly_revenue": 4880,
    "total_posts": 5000,
    "posts_week": 350,
    "active_deals": 25,
    "pending_deals": 5,
    "upcoming_amas": 3,
    "total_courses": 15,
    "total_events": 8,
    "pending_verifications": 12
  }
}
```

---

## Achievements API

Achievements are automatically awarded based on user activity.

### Available Achievements

| ID | Name | Description | Criteria |
|----|------|-------------|----------|
| first_post | First Post | Created your first post | 1 post |
| prolific_poster | Prolific Poster | Created 10 posts | 10 posts |
| thought_leader | Thought Leader | Created 50 posts | 50 posts |
| first_follower | First Follower | Gained your first follower | 1 follower |
| influencer | Influencer | Gained 100 followers | 100 followers |
| first_like | First Like | Received your first like | 1 like |
| popular | Popular | Received 100 likes | 100 likes |
| viral | Viral | Received 1000 likes | 1000 likes |
| deal_explorer | Deal Explorer | Explored your first deal | 1 deal interest |
| course_starter | Course Starter | Enrolled in your first course | 1 enrollment |
| learning_streak | Learning Streak | Enrolled in 5 courses | 5 enrollments |
| early_adopter | Early Adopter | Among first 100 users | User ID ≤ 100 |
| premium_member | Premium Member | Subscribed to Pro/Elite | Premium tier |

### GET /dashboard
Achievements are displayed on the user dashboard automatically.

---

## Filtering & Sorting API

### Deals Filtering

**GET /deals**

**Query Parameters:**
| Field | Type | Options | Description |
|-------|------|---------|-------------|
| type | string | real_estate, private_equity, venture_capital, hedge_fund, crypto, other | Deal type filter |
| min_investment | int | - | Minimum investment amount |
| max_investment | int | - | Maximum investment amount |
| sort | string | newest, popular, ending_soon | Sort order |

**Example:**
```
GET /deals?type=real_estate&min_investment=10000&sort=popular
```

---

### Courses Filtering

**GET /courses**

**Query Parameters:**
| Field | Type | Options | Description |
|-------|------|---------|-------------|
| category | string | investing, real_estate, tax, retirement, business | Category filter |
| level | string | beginner, intermediate, advanced | Difficulty level |
| price | string | free, paid | Price filter |
| sort | string | newest, popular, rating | Sort order |

**Example:**
```
GET /courses?category=investing&level=beginner&price=free
```

---

### Events Filtering

**GET /events**

**Query Parameters:**
| Field | Type | Options | Description |
|-------|------|---------|-------------|
| type | string | webinar, workshop, conference, networking | Event type |
| date | string | upcoming, past, this_week, this_month | Date filter |
| sort | string | date, popular | Sort order |

**Example:**
```
GET /events?type=webinar&date=upcoming
```

---

### Rooms Filtering

**GET /rooms**

**Query Parameters:**
| Field | Type | Options | Description |
|-------|------|---------|-------------|
| category | string | Various room categories | Category filter |
| q | string | - | Search query |
| sort | string | popular, newest, alphabetical, active | Sort order |

**Example:**
```
GET /rooms?category=Real%20Estate&sort=active&q=investing
```

---

## Email Digest API

Email digests are sent automatically via scheduler.

### Digest Types

| Type | Frequency | Content |
|------|-----------|---------|
| daily | Every 24 hours | Trending posts, new deals, upcoming AMAs |
| weekly | Every 7 days | Week summary, top content, events |

### User Preferences

Users can configure digest preferences at `/notifications/preferences`:
- Enable/disable email digests
- Choose frequency (daily/weekly/none)

---

## Admin Features API

### GET /admin/users
List all users (admin only).

**Query Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| page | int | Page number |
| search | string | Search by username/email |
| role | string | Filter by role |

---

### POST /admin/users/<id>/toggle-admin
Toggle admin status for user.

**Response:**
```json
{
  "success": true,
  "is_admin": true
}
```

---

### POST /admin/users/<id>/toggle-ban
Toggle ban status for user.

**Response:**
```json
{
  "success": true,
  "is_banned": true
}
```

---

### DELETE /admin/users/<id>
Delete user account (cannot delete self or other admins).

**Response:**
```json
{
  "success": true
}
```

---

## Dark Mode API

Dark mode is handled client-side via JavaScript.

### Toggle Mechanism

```javascript
// Toggle dark mode
document.getElementById('darkModeToggle').addEventListener('click', function() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
});

// Load preference on page load
if (localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
}
```

### CSS Variables

```css
:root {
  --bg-primary: #ffffff;
  --text-primary: #212529;
  --card-bg: #ffffff;
}

.dark-mode {
  --bg-primary: #1a1a2e;
  --text-primary: #e4e4e4;
  --card-bg: #16213e;
}
```

---

## Error Responses

All API endpoints return consistent error responses:

### 400 Bad Request
```json
{
  "error": "Invalid request parameters",
  "details": "tier must be 'pro' or 'elite'"
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "error": "Admin access required"
}
```

### 404 Not Found
```json
{
  "error": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred"
}
```

---

## Rate Limiting

API endpoints are subject to rate limiting:
- Standard users: 100 requests/minute
- Premium users: 500 requests/minute
- Admin users: Unlimited

---

## Webhooks

MedInvest can send webhooks to external systems.

### Supported Events

| Event | Description |
|-------|-------------|
| user.created | New user registered |
| user.verified | User verification completed |
| subscription.created | New subscription started |
| subscription.cancelled | Subscription cancelled |
| deal.interest | User expressed deal interest |
| post.created | New post published |

### Webhook Payload Format

```json
{
  "event": "subscription.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": 123,
    "tier": "pro",
    "interval": "month"
  }
}
```

---

## SDK Examples

### Python
```python
import requests

# Authenticate
session = requests.Session()
session.post('https://medinvest.app/auth/login', data={
    'email': 'user@example.com',
    'password': 'password123'
})

# Get notifications
response = session.get('https://medinvest.app/notifications/api/list')
notifications = response.json()
```

### JavaScript
```javascript
// Fetch notifications
fetch('/notifications/api/list', {
    credentials: 'include'
})
.then(response => response.json())
.then(data => {
    console.log('Notifications:', data.notifications);
    console.log('Unread count:', data.unread_count);
});
```

---

## Changelog

### v2.0.0 (Current)
- Added Stripe subscription integration
- Enhanced notification preferences
- Added achievements system
- Improved filtering and sorting
- Added email digests
- Enhanced admin analytics

### v1.0.0
- Initial release
- Basic social features
- User authentication
- Investment deals and courses
