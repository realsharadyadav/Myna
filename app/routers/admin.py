import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import ai, embeddings, models, schemas
from ..database import (
    get_db,
    get_default_embedding_model,
    get_default_search_model,
    get_default_vision_model,
    get_retain_uploaded_images,
    set_default_embedding_model,
    set_default_search_model,
    set_default_vision_model,
    set_retain_uploaded_images,
)
from ..sample_data import CSV_HEADERS, build_shops, shops_to_csv_rows

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    shop_count = db.query(func.count(models.Shop.shop_id)).scalar()
    item_count = db.query(func.count(models.Item.item_id)).scalar()
    recent_shops = (
        db.query(models.Shop)
        .order_by(models.Shop.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "total_shops": shop_count,
        "total_items": item_count,
        "recent_shops": [
            {
                "shop_id": s.shop_id,
                "name": s.name,
                "created_at": s.created_at.isoformat(),
            }
            for s in recent_shops
        ],
    }


# ---------------------------------------------------------------------------
# Shop list / detail / moderation
# ---------------------------------------------------------------------------

@router.get("/shops", response_model=list[schemas.ShopOut])
def list_shops(
    q: str = Query("", description="Search by shop name or address"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(models.Shop)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Shop.name.ilike(pattern),
                models.Shop.shopkeeper.ilike(pattern),
                models.Shop.address.ilike(pattern),
                models.Shop.phone.ilike(pattern),
            )
        )
    return (
        query.order_by(models.Shop.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/shops/{shop_id}", response_model=schemas.ShopOut)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


@router.patch("/shops/{shop_id}", response_model=schemas.ShopOut)
def update_shop(shop_id: int, payload: schemas.ShopUpdate, db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/shops/{shop_id}", status_code=204)
def delete_shop(shop_id: int, db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    db.delete(shop)
    db.commit()


@router.get("/shops/{shop_id}/items", response_model=list[schemas.ItemOut])
def list_shop_items(shop_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Shop, shop_id):
        raise HTTPException(404, "Shop not found")
    return (
        db.query(models.Item)
        .filter(models.Item.shop_id == shop_id)
        .order_by(models.Item.created_at.desc())
        .all()
    )


@router.get("/items", response_model=list[schemas.ItemOut])
def list_all_items(
    q: str = Query("", description="Search by item name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get all items across all shops (admin global view)."""
    query = db.query(models.Item).join(models.Shop)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(models.Item.name.ilike(pattern))
    return (
        query.order_by(models.Item.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.patch("/items/{item_id}", response_model=schemas.ItemOut)
def update_any_item(item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
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


@router.delete("/items/{item_id}", status_code=204)
def delete_any_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()


# ---------------------------------------------------------------------------
# LLM provider settings
# ---------------------------------------------------------------------------

@router.get("/llm/providers")
def llm_providers():
    """Which providers have keys configured. Fetches real model lists
    from each provider's API."""
    return {
        "providers": ai.fetch_all_models(),
        "configured_providers": ai.configured_providers(),
    }


@router.get("/llm/models")
def llm_models():
    """Fetch all available vision models from configured providers (real API lists)."""
    return {"models": ai.fetch_all_models()}


@router.get("/llm/embedding-models")
def llm_embedding_models():
    """Fetch embedding-capable models (separate from vision/text models above)."""
    return {"models": embeddings.fetch_embedding_models()}


# ---------------------------------------------------------------------------
# Admin settings
# ---------------------------------------------------------------------------

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return {
        "retain_uploaded_images": get_retain_uploaded_images(db),
        "default_vision_model": get_default_vision_model(db),
        "default_search_model": get_default_search_model(db),
        "default_embedding_model": get_default_embedding_model(db),
    }


@router.patch("/settings")
def update_settings(payload: dict, db: Session = Depends(get_db)):
    if "retain_uploaded_images" in payload:
        set_retain_uploaded_images(db, bool(payload["retain_uploaded_images"]))
    if "default_vision_model" in payload:
        set_default_vision_model(db, payload["default_vision_model"])
    if "default_search_model" in payload:
        set_default_search_model(db, payload["default_search_model"])
    if "default_embedding_model" in payload:
        set_default_embedding_model(db, payload["default_embedding_model"])
    return get_settings(db)


# ---------------------------------------------------------------------------
# Semantic search (embeddings backfill)
# ---------------------------------------------------------------------------

@router.get("/embeddings/status")
def embeddings_status(db: Session = Depends(get_db)):
    total = db.query(func.count(models.Item.item_id)).scalar() or 0
    embedded = (
        db.query(func.count(models.Item.item_id))
        .filter(models.Item.embedding != "", models.Item.embedding.isnot(None))
        .scalar()
    ) or 0
    default_model = get_default_embedding_model(db) or ""
    stale = (
        db.query(func.count(models.Item.item_id))
        .filter(
            (models.Item.embedding != "") & (models.Item.embedding.isnot(None)),
            models.Item.embedding_model != default_model,
        )
        .scalar()
    ) or 0
    return {
        "enabled": embeddings.enabled(),
        "total_items": total,
        "embedded_items": embedded,
        "pending_items": total - embedded,
        "stale_items": stale,
    }


@router.post("/embeddings/backfill")
def embeddings_backfill(db: Session = Depends(get_db)):
    """Embed all items missing a vector or using a stale embedding model."""
    done = embeddings.backfill(db)
    return {"embedded": done}

@router.get("/import/template")
def import_template(sample: bool = Query(False)):
    """CSV template. With ?sample=1, pre-filled with demo data you can tweak."""
    shops = build_shops(50) if sample else [{
        "name": "Sharma General Store",
        "shopkeeper": "Ramesh Sharma",
        "lat": 19.0760,
        "long": 72.8777,
        "address": "Shop 4, Link Road, Andheri West, Mumbai",
        "phone": "9820012345",
        "items": [
            ("Parle-G Gold Biscuits 100g", "Snacks"),
            ("Tata Salt 1kg", "Grocery"),
        ],
    }]
    rows = shops_to_csv_rows(shops)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    filename = "myna_sample_data.csv" if sample else "myna_import_template.csv"
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/csv")
def import_csv(
    file: UploadFile = File(...),
    replace: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Import shops + items from a CSV file.

    Flat format — one row per item, shop fields repeated:
    shop_name, shopkeeper, lat, long, address, phone, item_name, category

    Matching is by shop_name: existing shops are updated, new ones created.
    If replace=true, all existing shops/items are wiped first.
    """
    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "Empty CSV — missing header row")

    header_lower = {h.strip().lower(): h for h in reader.fieldnames if h}
    def col(row, name):  # tolerate case/spaces in header names
        original = header_lower.get(name.lower())
        return (row.get(original) or "").strip() if original else ""

    required = ["shop_name", "lat", "long"]
    missing = [h for h in required if h not in header_lower]
    if missing:
        raise HTTPException(
            400,
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected: {', '.join(CSV_HEADERS)}",
        )

    if replace:
        db.query(models.Item).delete()
        db.query(models.Shop).delete()
        db.commit()

    seen: set[str] = set()
    shops_by_name: dict[str, models.Shop] = {}
    created = updated = items_added = 0
    errors: list[str] = []

    for line_no, row in enumerate(reader, start=2):
        if not any((col(row, h) or "") for h in CSV_HEADERS):
            continue  # blank line

        shop_name = col(row, "shop_name")
        lat_raw = col(row, "lat")
        lon_raw = col(row, "long")
        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except ValueError:
            errors.append(f"Row {line_no}: bad lat/long ('{lat_raw}', '{lon_raw}')")
            continue

        if not shop_name:
            errors.append(f"Row {line_no}: missing shop_name")
            continue

        shop = shops_by_name.get(shop_name)
        if shop is None and shop_name not in seen:
            shop = db.query(models.Shop).filter(models.Shop.name == shop_name).first()
            if shop is None:
                shop = models.Shop(
                    name=shop_name,
                    shopkeeper=col(row, "shopkeeper"),
                    lat=lat,
                    long=lon,
                    address=col(row, "address"),
                    phone=col(row, "phone"),
                )
                db.add(shop)
                db.flush()
                created += 1
            else:
                updated += 1
            seen.add(shop_name)
        elif shop is None:
            # shop_name seen earlier in this file but vanished from cache —
            # refetch it so items don't error out
            shop = db.query(models.Shop).filter(models.Shop.name == shop_name).first()

        if shop is not None:
            # Merge: keep existing values unless the CSV provides new ones.
            if col(row, "shopkeeper"):
                shop.shopkeeper = col(row, "shopkeeper")
            if col(row, "address"):
                shop.address = col(row, "address")
            if col(row, "phone"):
                shop.phone = col(row, "phone")
            shop.lat = lat
            shop.long = lon
        shops_by_name[shop_name] = shop

        item_name = col(row, "item_name")
        if item_name:
            db.add(models.Item(
                shop_id=shop.shop_id,
                name=item_name,
                category=col(row, "category"),
            ))
            items_added += 1

    db.commit()
    embeddings.invalidate_cache()
    return {
        "created": created,
        "updated": updated,
        "items": items_added,
        "errors": errors[:20],
        "total_errors": len(errors),
    }
