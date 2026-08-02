from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, models, schemas
from ..database import get_db
from ..storage import save_upload

router = APIRouter(prefix="/api/shops/{shop_id}/items", tags=["items"])


def _get_shop(shop_id: int, db: Session) -> models.Shop:
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


@router.get("", response_model=list[schemas.ItemOut])
def list_items(shop_id: int, db: Session = Depends(get_db)):
    _get_shop(shop_id, db)
    return (
        db.query(models.Item)
        .filter(models.Item.shop_id == shop_id)
        .order_by(models.Item.created_at.desc())
        .all()
    )


@router.post("", response_model=schemas.ItemOut)
def create_item(
    shop_id: int,
    name: str = Form(...),
    category: str = Form(""),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    _get_shop(shop_id, db)
    photo_url = save_upload(photo) if photo else ""
    item = models.Item(shop_id=shop_id, name=name, category=category, photo_url=photo_url)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.ItemOut)
def update_item(shop_id: int, item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item or item.shop_id != shop_id:
        raise HTTPException(404, "Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(shop_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item or item.shop_id != shop_id:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()


@router.post("/suggest", response_model=dict)
def suggest_item(shop_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db)):
    """Accept an item photo, save it, and return AI-suggested name/category."""
    _get_shop(shop_id, db)
    url = save_upload(photo)
    file_path = url.lstrip("/")
    name, category = ai.suggest_item(file_path)
    return {"name": name, "category": category, "photo_url": url}
