from fastapi import FastAPI
from .routers import auth, deals, webhooks
from .db import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MedInvest API", version="0.1.0")
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(deals.router, prefix="/deals", tags=["deals"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

@app.get("/")
def root():
    return {"status": "ok"}
