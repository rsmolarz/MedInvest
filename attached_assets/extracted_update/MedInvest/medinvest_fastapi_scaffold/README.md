# MedInvest FastAPI Scaffold

## Quick start on Replit
1. Create a new **Python** repl.
2. Upload this zip and extract. Ensure files appear at repo root.
3. In **Shell**: `pip install -r requirements.txt`
4. Add **Secrets**:
   - `SECRET_KEY` = supersecretdevkey_123456789
   - Optional: `STRIPE_API_KEY` = sk_test_4eC39HqLyjWDarjtT1zdp7dc
   - Optional: `STRIPE_WEBHOOK_SECRET` = whsec_test_1234567890
   - Optional: `PLAID_CLIENT_ID` = plaid_client_id_test
   - Optional: `PLAID_SECRET` = plaid_secret_test
   - Optional: `PERSONA_API_KEY` = persona_sandbox_api_key
5. Click **Run**. Open `/docs`.

## Local run
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
set SECRET_KEY=supersecretdevkey_123456789  # PowerShell; use export on Unix
uvicorn app.main:app --reload
```
Visit http://127.0.0.1:8000/docs

## Notes
- Uses SQLite by default. Override with `DATABASE_URL` (e.g., Postgres).
- Webhook endpoints are stubs for Stripe, Plaid, Persona.
