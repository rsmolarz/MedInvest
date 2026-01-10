from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    class Config:
        from_attributes = True

class DealCreate(BaseModel):
    title: str
    description: str
    min_investment: float

class DealOut(BaseModel):
    id: int
    title: str
    description: str
    min_investment: float
    class Config:
        from_attributes = True


# -----------------
# Advertising schemas
# -----------------


class AdAdvertiserCreate(BaseModel):
    name: str
    category: str = "other"
    compliance_status: str = "active"


class AdAdvertiserOut(BaseModel):
    id: int
    name: str
    category: str
    compliance_status: str

    class Config:
        from_attributes = True


class AdCampaignCreate(BaseModel):
    advertiser_id: int
    name: str
    start_at: datetime
    end_at: datetime
    daily_budget: float = 0
    targeting_json: dict | None = None


class AdCampaignOut(BaseModel):
    id: int
    advertiser_id: int
    name: str
    start_at: datetime
    end_at: datetime
    daily_budget: float
    targeting_json: str

    class Config:
        from_attributes = True


class AdCreativeCreate(BaseModel):
    campaign_id: int
    format: str  # feed | sidebar | deal_inline
    headline: str
    body: str = ""
    image_url: str | None = None
    cta_text: str = "Learn more"
    landing_url: str
    disclaimer_text: str = ""


class AdCreativeOut(BaseModel):
    id: int
    campaign_id: int
    format: str
    headline: str
    body: str
    image_url: str | None
    cta_text: str
    landing_url: str
    disclaimer_text: str
    is_active: bool

    class Config:
        from_attributes = True


class AdCreativeServe(BaseModel):
    id: int
    format: str
    headline: str
    body: str
    image_url: str | None
    cta_text: str
    disclaimer_text: str
    click_url: str


class AdServeResponse(BaseModel):
    creative: AdCreativeServe | None


class AdImpressionCreate(BaseModel):
    creative_id: int
    placement: str
    page_view_id: str | None = None
