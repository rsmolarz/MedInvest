from pydantic import BaseModel, EmailStr
from typing import Optional

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
