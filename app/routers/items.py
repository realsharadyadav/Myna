from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, catalog, embeddings, models, schemas
from ..database import get_db, get_default_embedding_model, get_default_vision_model, get_retain_uploaded_images
from ..storage import save_upload

router = APIRouter(prefix="/api/shops/{shop_id}/items", tags=["items"])

# Not shop-scoped — the catalogue is the same for everyone, so it lives on its
# own prefix and is included separately in main.py.
catalog_router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@catalog_router.get("", response_model=dict)
def get_catalog():
    """Categories and their common products, for the checkbox picker."""
    return {"categories": catalog.all_categories()}


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
    if local_path and not retain:
        Path(local_path).unlink(missing_ok=True)
    item = models.Item(shop_id=shop_id, name=name, category=category, photo_url=public_url)
    embeddings.embed_item(item, db)
    db.add(item)
    db.commit()
    db.refresh(item)
    embeddings.invalidate_cache()
    return item


@router.post("/bulk", response_model=schemas.BulkItemsResult)
def create_items_bulk(shop_id: int, payload: schemas.BulkItemsCreate, db: Session = Depends(get_db)):
    """Add many items in one request — what the category checkboxes submit.

    Names the shop already stocks are skipped rather than duplicated, so a
    shopkeeper can tick a category again later to pick up the few products
    they missed without ending up with two of everything.
    """
    _get_shop(shop_id, db)
    existing = {
        name.strip().lower()
        for (name,) in db.query(models.Item.name).filter(models.Item.shop_id == shop_id)
    }
    added: list[models.Item] = []
    skipped: list[str] = []
    for entry in payload.items:
        name = entry.name.strip()
        if not name:
            continue
        key = name.lower()
        if key in existing:
            skipped.append(name)
            continue
        existing.add(key)
        added.append(models.Item(
            shop_id=shop_id,
            name=name,
            category=(entry.category or "").strip() or catalog.suggest_category(name),
        ))
    if added:
        embeddings.embed_items(added, db)
        db.add_all(added)
        db.commit()
        for item in added:
            db.refresh(item)
        embeddings.invalidate_cache()
    return {"added": added, "skipped": skipped}


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
    """Read every product out of an item/shelf photo, then discard the photo
    if retention is off.

    Returns the full list under "items". "name"/"category" still carry the
    first match so older clients keep working.
    """
    _get_shop(shop_id, db)
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain)
    vision_model = get_default_vision_model(db)
    try:
        items, error = ai.suggest_items(local_path, model=vision_model)
    finally:
        if not retain:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass
    for item in items:
        if not item.get("category"):
            item["category"] = catalog.suggest_category(item["name"])
    return {
        "items": items,
        "name": items[0]["name"] if items else "",
        "category": items[0]["category"] if items else "",
        "error": error,
        "photo_url": public_url,
    }
