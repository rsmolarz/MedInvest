# Analytics Dashboard Spec (v1)

## Purpose
Track activation + retention for a verified-doctor investing community. This dashboard is for operating decisions, not vanity metrics.

## North-star metrics (weekly)
- **Verified WAU**: verified doctors active in the last 7 days
- **Deal WAU**: verified doctors who created OR commented on a deal in last 7 days
- **Time-to-first-value**: median time from verification -> first meaningful action (deal post OR endorsed comment)

## Activation funnel
1. Signup
2. Verification submitted
3. Verified
4. First meaningful action
   - create deal
   - comment on deal
   - endorse comment/post
5. Return within 7 days

## Core retention
- D1 / D7 / D30 for verified users
- Weekly cohort retention chart (verified users)

## Content metrics
- Deals created per week
- Comments per deal (median, p75)
- Endorsements per deal (median)
- AI jobs created/completed
- AI completion latency (p50/p95)

## Trust + quality
- Verification queue size
- Verification SLA (submit -> verified) p50/p95
- Reports per week (later)
- Admin actions per week (approvals/rejections)

## Growth
- Invites issued / accepted
- Invite conversion rate
- Invite expiration rate

## Data sources (v1)
- users: created_at, verification_status, verified_at, last_seen, reputation_score, invite_credits
- deal_details: created_at, asset_class, status
- comments: created_at, post_id, author_id
- reputation_events: created_at, event_type, user_id, related_post_id
- ai_jobs: created_at, status, started_at, completed_at, created_by_user_id
- invites: created_at, status, accepted_at, expires_at
- notifications: created_at, notification_type, is_read

## Implementation approach
### Option A (fast): SQL queries + server-rendered admin page
- Add `/api/admin/analytics/overview`
- Calculate in SQL or Python and return JSON

### Option B (robust): event stream + warehouse
- Emit events to a log table (`telemetry_events`) and ETL to ClickHouse/BigQuery

## Recommended v1 endpoints
- `GET /api/admin/analytics/overview`
- `GET /api/admin/analytics/cohorts?window=7|30`
- `GET /api/admin/analytics/verification`
- `GET /api/admin/analytics/content`

## Minimal UI (admin-only)
- Overview cards: Verified WAU, Deal WAU, Time-to-first-value, Verification SLA
- Trend charts: deals/week, comments/week, invites accepted/week, AI completions/week
- Tables: pending verification queue, top deals (signal_score), top commenters (reputation delta)
