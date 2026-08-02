from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, embeddings, models, schemas
from ..database import get_db, get_default_embedding_model, get_default_vision_model, get_retain_uploaded_images
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
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain) if photo else ("", "")
    item = models.Item(shop_id=shop_id, name=name, category=category, photo_url=public_url)
    vision_model = get_default_vision_model(db)
    if photo and retain:
        try:
            ai.suggest_item(local_path, model=vision_model)
        finally:
            pass
    embeddings.embed_item(item, db)
    db.add(item)
    db.commit()
    db.refresh(item)
    embeddings.invalidate_cache()
    return item


@router.patch("/{item_id}", response_model=schemas.ItemOut)
def update_item(shop_id: int, item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item or item.shop_id != shop_id:
        raise HTTPException(404, "Item not found")
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(item, field, value)
    if "name" in fields or "category" in fields:
        embeddings.embed_item(item, db)
    db.commit()
    db.refresh(item)
    embeddings.invalidate_cache()
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
    """Accept an item photo, use it for AI suggestion, then discard if retention is off."""
    _get_shop(shop_id, db)
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain)
    vision_model = get_default_vision_model(db)
    try:
        name, category = ai.suggest_item(local_path, model=vision_model)
    finally:
        if not retain:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass
    return {"name": name, "category": category, "photo_url": public_url}
