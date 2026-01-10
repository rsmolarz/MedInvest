from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..deps import get_db, get_current_user
from ..models import AdAdvertiser, AdCampaign, AdCreative, AdImpression, AdClick, User
from ..schemas import (
    AdAdvertiserCreate,
    AdAdvertiserOut,
    AdCampaignCreate,
    AdCampaignOut,
    AdCreativeCreate,
    AdCreativeOut,
    AdServeResponse,
    AdImpressionCreate,
)


router = APIRouter()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _sign(payload_b64: str) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256)
    return _b64url(mac.digest())


def _make_click_token(*, creative_id: int, user_id: int) -> str:
    payload = {
        "creative_id": creative_id,
        "user_id": user_id,
        "ts": int(datetime.utcnow().timestamp()),
    }
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def _parse_click_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid click token")
    if not hmac.compare_digest(_sign(payload_b64), sig):
        raise HTTPException(status_code=400, detail="Invalid click token")
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    return payload


def _load_targeting(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _matches_targeting(*, targeting: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Lightweight targeting matcher.

    Supported keys (all optional):
      - specialty: ["ENT", "IM"]
      - role: ["attending", "resident"]
      - state: ["TX", "CA"]
      - placement: ["feed", "sidebar", "deal_inline"]
      - keywords_any: ["self-storage", "ASC"]
      - exclude_user_ids: [1,2,3]
    """
    if not targeting:
        return True

    # Hard excludes
    if ctx.get("user_id") in set(targeting.get("exclude_user_ids", [])):
        return False

    def _in_list(key: str) -> bool:
        allowed = targeting.get(key)
        if not allowed:
            return True
        return ctx.get(key) in set(allowed)

    if not _in_list("specialty"):
        return False
    if not _in_list("role"):
        return False
    if not _in_list("state"):
        return False
    if not _in_list("placement"):
        return False

    keywords_any = targeting.get("keywords_any")
    if keywords_any:
        hay = (ctx.get("keywords") or "").lower()
        if not any(k.lower() in hay for k in keywords_any):
            return False

    return True


def _require_admin(user: User) -> None:
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin required")


# --------------------
# Admin: CRUD (minimal)
# --------------------


@router.post("/admin/advertisers", response_model=AdAdvertiserOut)
def create_advertiser(
    payload: AdAdvertiserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = AdAdvertiser(name=payload.name, category=payload.category, compliance_status=payload.compliance_status)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/admin/advertisers", response_model=list[AdAdvertiserOut])
def list_advertisers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return db.query(AdAdvertiser).order_by(AdAdvertiser.id.desc()).limit(200).all()


@router.post("/admin/campaigns", response_model=AdCampaignOut)
def create_campaign(
    payload: AdCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = AdCampaign(
        advertiser_id=payload.advertiser_id,
        name=payload.name,
        start_at=payload.start_at,
        end_at=payload.end_at,
        daily_budget=payload.daily_budget,
        targeting_json=json.dumps(payload.targeting_json or {}),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/admin/creatives", response_model=AdCreativeOut)
def create_creative(
    payload: AdCreativeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = AdCreative(
        campaign_id=payload.campaign_id,
        format=payload.format,
        headline=payload.headline,
        body=payload.body,
        image_url=payload.image_url,
        cta_text=payload.cta_text,
        landing_url=payload.landing_url,
        disclaimer_text=payload.disclaimer_text,
        is_active=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/admin/campaigns", response_model=list[AdCampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return db.query(AdCampaign).order_by(AdCampaign.id.desc()).limit(200).all()


@router.get("/admin/creatives", response_model=list[AdCreativeOut])
def list_creatives(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return db.query(AdCreative).order_by(AdCreative.id.desc()).limit(200).all()


# --------------------
# Public: serve + track
# --------------------


@router.get("/serve", response_model=AdServeResponse)
def serve_ad(
    placement: str,
    keywords: str | None = None,
    specialty: str | None = None,
    role: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    ctx = {
        "user_id": current_user.id,
        "placement": placement,
        "keywords": keywords or "",
        "specialty": specialty,
        "role": role,
        "state": state,
    }

    # Active creatives in active campaigns.
    q = (
        db.query(AdCreative, AdCampaign)
        .join(AdCampaign, AdCreative.campaign_id == AdCampaign.id)
        .filter(AdCreative.is_active == True)  # noqa: E712
        .filter(AdCampaign.start_at <= now)
        .filter(AdCampaign.end_at >= now)
        .filter(AdCreative.format == placement)
        .order_by(AdCreative.id.desc())
    )

    chosen: AdCreative | None = None
    for creative, campaign in q.limit(50).all():
        targeting = _load_targeting(campaign.targeting_json)
        if _matches_targeting(targeting=targeting, ctx=ctx):
            chosen = creative
            break

    if not chosen:
        return {"creative": None}

    token = _make_click_token(creative_id=chosen.id, user_id=current_user.id)
    return {
        "creative": {
            "id": chosen.id,
            "format": chosen.format,
            "headline": chosen.headline,
            "body": chosen.body,
            "image_url": chosen.image_url,
            "cta_text": chosen.cta_text,
            "disclaimer_text": chosen.disclaimer_text,
            "click_url": f"/ads/click/{token}",
        }
    }


@router.post("/impression")
def log_impression(
    payload: AdImpressionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Idempotency guard: one impression per user/creative/page_view_id
    if payload.page_view_id:
        existing = (
            db.query(AdImpression)
            .filter(AdImpression.user_id == current_user.id)
            .filter(AdImpression.creative_id == payload.creative_id)
            .filter(AdImpression.page_view_id == payload.page_view_id)
            .first()
        )
        if existing:
            return {"status": "ok"}

    obj = AdImpression(
        creative_id=payload.creative_id,
        user_id=current_user.id,
        placement=payload.placement,
        page_view_id=payload.page_view_id,
        created_at=datetime.utcnow(),
    )
    db.add(obj)
    db.commit()
    return {"status": "ok"}


@router.get("/click/{token}")
def click_redirect(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = _parse_click_token(token)
    if payload.get("user_id") != current_user.id:
        # Prevent token sharing; still allow redirect without logging.
        raise HTTPException(status_code=403, detail="Invalid user")

    creative_id = int(payload.get("creative_id"))
    creative = db.query(AdCreative).filter(AdCreative.id == creative_id).first()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    db.add(
        AdClick(
            creative_id=creative_id,
            user_id=current_user.id,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return RedirectResponse(url=creative.landing_url)
