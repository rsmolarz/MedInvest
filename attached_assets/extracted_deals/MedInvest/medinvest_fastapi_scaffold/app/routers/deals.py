from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import schemas
from ..models import Deal
from ..deps import get_db, get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.DealOut)
def create_deal(deal: schemas.DealCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = Deal(title=deal.title, description=deal.description, min_investment=deal.min_investment)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d

@router.get("/", response_model=list[schemas.DealOut])
def list_deals(db: Session = Depends(get_db)):
    return db.query(Deal).all()
