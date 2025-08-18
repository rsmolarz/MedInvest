from pydantic import BaseModel
import os

class Settings(BaseModel):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    STRIPE_API_KEY: str | None = os.getenv("STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET: str | None = os.getenv("STRIPE_WEBHOOK_SECRET")
    PLAID_CLIENT_ID: str | None = os.getenv("PLAID_CLIENT_ID")
    PLAID_SECRET: str | None = os.getenv("PLAID_SECRET")
    PERSONA_API_KEY: str | None = os.getenv("PERSONA_API_KEY")

settings = Settings()
