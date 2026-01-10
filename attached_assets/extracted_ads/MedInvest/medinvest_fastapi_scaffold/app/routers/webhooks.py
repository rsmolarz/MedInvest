from fastapi import APIRouter, Header, HTTPException, Request
from ..core.config import settings

router = APIRouter()

@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(400, "STRIPE_WEBHOOK_SECRET not set")
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe-Signature header")
    return {"received": True}

@router.post("/plaid")
async def plaid_webhook(request: Request):
    body = await request.json()
    return {"ok": True, "type": body.get("webhook_type")}

@router.post("/persona")
async def persona_webhook(request: Request):
    body = await request.json()
    return {"ok": True, "event": body.get("data", {}).get("attributes", {}).get("name")}
