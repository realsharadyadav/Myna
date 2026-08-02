from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, models, schemas
from ..database import get_db
from ..geo import reverse_geocode
from ..storage import save_upload

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.post("", response_model=schemas.ShopOut)
def create_shop(payload: schemas.ShopCreate, db: Session = Depends(get_db)):
    address = payload.address or reverse_geocode(payload.lat, payload.long)
    shop = models.Shop(
        name=payload.name,
        lat=payload.lat,
        long=payload.long,
        address=address,
        phone=payload.phone or "",
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/{shop_id}", response_model=schemas.ShopOut)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


@router.patch("/{shop_id}", response_model=schemas.ShopOut)
def update_shop(shop_id: int, payload: schemas.ShopUpdate, db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


@router.post("/{shop_id}/photo", response_model=schemas.ShopOut)
def upload_shop_photo(shop_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    shop.photo_url = save_upload(photo)
    db.commit()
    db.refresh(shop)
    return shop


@router.post("/onboard/photo", response_model=schemas.AISuggestion)
def onboard_photo(photo: UploadFile = File(...)):
    """Accept a signage photo, save it, and return an AI-suggested shop name."""
    url = save_upload(photo)
    file_path = url.lstrip("/")
    suggestion = ai.suggest_shop_name(file_path)
    return {"suggestion": suggestion}


@router.get("/geocode/reverse", response_model=dict)
def geocode_reverse(lat: float, long: float):
    return {"address": reverse_geocode(lat, long)}
