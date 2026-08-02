from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, models, schedule, schemas
from ..database import get_db, get_default_vision_model, get_retain_uploaded_images
from ..geo import reverse_geocode
from ..storage import save_upload

router = APIRouter(prefix="/api/shops", tags=["shops"])

SHOP_TYPES = {"fixed", "mobile"}


def _normalise_type(value: str | None) -> str:
    return value if value in SHOP_TYPES else "fixed"


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
        shop_type=_normalise_type(payload.shop_type),
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
        suggestion = ai.suggest_shop_name(local_path, model=vision_model)
    finally:
        if not retain:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass
    return {"suggestion": suggestion}


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
        if field == "shop_type":
            value = _normalise_type(value)
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


# ---------------------------------------------------------------------------
# Stops — where a mobile vendor (thela/cart) stands, and when
# ---------------------------------------------------------------------------

def _get_shop(db: Session, shop_id: int) -> models.Shop:
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


def _validate_stop(day_of_week: int | None, start_time: str | None, end_time: str | None) -> None:
    if day_of_week is not None and not (day_of_week == schedule.EVERY_DAY or 0 <= day_of_week <= 6):
        raise HTTPException(422, "day_of_week must be 0-6 (Mon-Sun) or -1 for every day")
    for label, value in (("start_time", start_time), ("end_time", end_time)):
        if value and schedule.parse_hhmm(value) is None:
            raise HTTPException(422, f"{label} must be in HH:MM 24-hour format")
    start, end = schedule.parse_hhmm(start_time or ""), schedule.parse_hhmm(end_time or "")
    if start is not None and end is not None and end <= start:
        raise HTTPException(422, "end_time must be after start_time")


@router.get("/{shop_id}/stops", response_model=list[schemas.StopOut])
def list_stops(shop_id: int, db: Session = Depends(get_db)):
    """A vendor's stops, soonest first — 'here now' before 'comes on Friday'."""
    shop = _get_shop(db, shop_id)
    views = [schedule.stop_view(s) for s in shop.stops]
    views.sort(key=lambda v: (v["rank"], v["start_time"] or "99:99"))
    return views


@router.post("/{shop_id}/stops", response_model=schemas.StopOut)
def add_stop(shop_id: int, payload: schemas.StopCreate, db: Session = Depends(get_db)):
    shop = _get_shop(db, shop_id)
    _validate_stop(payload.day_of_week, payload.start_time, payload.end_time)
    address = payload.address or reverse_geocode(payload.lat, payload.long)
    stop = models.ShopStop(
        shop_id=shop.shop_id,
        label=payload.label or "",
        lat=payload.lat,
        long=payload.long,
        address=address,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time or "",
        end_time=payload.end_time or "",
        note=payload.note or "",
    )
    # Adding a round is itself the statement that this vendor moves around, so
    # the shop flips to mobile instead of needing a separate toggle first.
    if shop.shop_type != "mobile":
        shop.shop_type = "mobile"
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return schedule.stop_view(stop)


@router.patch("/{shop_id}/stops/{stop_id}", response_model=schemas.StopOut)
def update_stop(shop_id: int, stop_id: int, payload: schemas.StopUpdate, db: Session = Depends(get_db)):
    stop = db.get(models.ShopStop, stop_id)
    if not stop or stop.shop_id != shop_id:
        raise HTTPException(404, "Stop not found")
    changes = payload.model_dump(exclude_unset=True)
    _validate_stop(
        changes.get("day_of_week"),
        changes.get("start_time", stop.start_time),
        changes.get("end_time", stop.end_time),
    )
    for field, value in changes.items():
        setattr(stop, field, value)
    db.commit()
    db.refresh(stop)
    return schedule.stop_view(stop)


@router.delete("/{shop_id}/stops/{stop_id}")
def delete_stop(shop_id: int, stop_id: int, db: Session = Depends(get_db)):
    stop = db.get(models.ShopStop, stop_id)
    if not stop or stop.shop_id != shop_id:
        raise HTTPException(404, "Stop not found")
    db.delete(stop)
    db.commit()
    return {"deleted": True}


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
