# GitHub Issues (Sprint Backlog)

> Copy/paste each issue into GitHub. Suggested labels in [brackets].

## 1. Deal Wizard (4-step) + Auto AI Analyst
[feature][frontend][backend][p0]
**Goal:** Verified doctor posts a deal in <90s; AI analysis runs automatically.

**Backend**
- Extend `POST /api/deals` to accept wizard payload (title, visibility, deal fields, auto_ai)
- Ensure `auto_ai=true` enqueues `AiJob(job_type=analyze_deal, deal_id=...)` idempotently

**Frontend**
- Create `/deals/new` wizard (4 steps)
- Redirect to `/deals/{id}` and show “AI running” state

**Acceptance**
- Unverified users get 403
- Deal created <2s
- AI job created automatically
- Deal detail shows analysis when complete

## 2. Invites: Issue + List + Accept
[feature][backend][frontend][p0]
**Goal:** Invite-only growth with credits and expiration.

**Backend**
- Add `Invite` model and endpoints:
  - `GET/POST /api/invites`
  - `POST /api/invites/accept`
- Enforce `invite_credits` for non-admin users
- Expire invites when `expires_at < now`

**Frontend**
- `/invites` page:
  - show remaining credits
  - create invite (optional email)
  - copy invite link
  - list issued invites w/ status

**Acceptance**
- Credits decrement on creation
- Invite expires after 14 days
- Accepting invite updates status to `accepted`

## 3. Deals Feed: Trending + New
[feature][backend][frontend][p0]
**Goal:** Feed shows signal; trending uses reputation-weighted score.

**Backend**
- `GET /api/deals?sort=trending` returns top deals with `signal_score`
- `GET /api/deals?sort=new` returns newest deals

**Frontend**
- `/deals` page with tabs:
  - Trending
  - New
- “Post a Deal” CTA

**Acceptance**
- Trending results include `signal_score`
- New results are strictly created_at desc

## 4. Weekly Digest Generator + APIs
[feature][backend][p1]
**Goal:** Weekly digest persists top deals/comments and notifies verified users.

**Backend**
- Add `Digest` + `DigestItem` models
- Add:
  - `GET /api/digests/latest`
  - `GET /api/digests/{id}`
- Implement job function `generate_weekly_digest(7 days)`

**Acceptance**
- If no digest exists, latest returns 404
- Digest returns items in stable order
- Digest includes one summary item

## 5. Digest UI
[feature][frontend][p1]
**Goal:** Verified users can open the digest and navigate to deals.

**Frontend**
- Digest card component
- `/digests/[digestId]` page

**Acceptance**
- Loads latest digest
- Deal links work
- Renders summary text

## 6. Analytics Dashboard (Admin-only) – Design + v1 Endpoint
[feature][admin][p1]
**Goal:** Ops visibility into activation and verification throughput.

**Backend**
- `GET /api/admin/analytics/overview` returns:
  - verified WAU
  - deal WAU
  - time-to-first-value p50
  - verification SLA p50/p95
  - invites issued/accepted 7d

**Frontend**
- `/admin/analytics` simple page

**Acceptance**
- Only admins can access
- Numbers match DB truth
