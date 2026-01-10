# Frontend scaffolds (Next.js)

This repo is currently a Flask app with server-rendered templates. A minimal Next.js frontend scaffold is included under `frontend/` to accelerate:

- Admin verification throughput (queue + review)
- Deal detail + “AI Analyst” panel (enqueue + poll + render)

It is intentionally light on styling and assumes **cookie-based Flask session auth** (fetch uses `credentials: "include"`).

## Run

1. Start Flask (default port 5000):

```bash
python app.py
```

2. Start the Next.js dev server:

```bash
cd frontend
npm install
npm run dev
```

3. Optional: set API base

If Next.js is not on the same origin as Flask, set:

```bash
export NEXT_PUBLIC_API_BASE="http://localhost:5000"
```

## Pages

- `/admin/verification` → uses `GET /api/admin/verification/pending`
- `/admin/verification/[userId]` → uses `GET /api/admin/verification/:userId`, `POST /approve`, `POST /reject`
- `/deals/[dealId]` → uses `GET /api/deals/:dealId`, AI panel uses `POST /api/ai/jobs` + `GET /api/ai/jobs/:id`

## Notes

- If you move to JWT auth, update `frontend/lib/api.ts` to attach an `Authorization: Bearer` header.
- The “AI Analyst” button uses an `Idempotency-Key` header; the backend will re-use queued/running jobs to avoid duplicates.
