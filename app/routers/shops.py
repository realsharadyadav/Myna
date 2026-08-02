from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, models, schemas
from ..database import get_db, get_default_vision_model, get_retain_uploaded_images
from ..geo import reverse_geocode
from ..storage import save_upload

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.post("", response_model=schemas.ShopOut)
def create_shop(payload: schemas.ShopCreate, db: Session = Depends(get_db)):
    address = payload.address or reverse_geocode(payload.lat, payload.long)
    shop = models.Shop(
        name=payload.name,
        shopkeeper=payload.shopkeeper or "",
        lat=payload.lat,
        long=payload.long,
        address=address,
        phone=payload.phone or "",
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


# Literal routes first — otherwise /{shop_id} matches "onboard"/"geocode"
# and the request fails as an int-parsing error before reaching them.
@router.post("/onboard/photo", response_model=schemas.AISuggestion)
def onboard_photo(photo: UploadFile = File(), db: Session = Depends(get_db)):
    """Accept a signage photo, use it for OCR, then discard if retention is off."""
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain)
    vision_model = get_default_vision_model(db)
    try:
        suggestion, error = ai.suggest_shop_name_detailed(local_path, model=vision_model)
    finally:
        if not retain:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass
    return {"suggestion": suggestion, "error": error}


@router.get("/geocode/reverse", response_model=dict)
def geocode_reverse(lat: float, long: float):
    return {"address": reverse_geocode(lat, long)}


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
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain)
    if retain:
        shop.photo_url = public_url
    else:
        Path(local_path).unlink(missing_ok=True)
    db.commit()
    db.refresh(shop)
    return shop
