from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import ai, embeddings, food, models, schemas, vision_check
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
    # Reported/hidden counts sit on the dashboard so a queue of flagged
    # listings can't quietly build up unseen — the whole point of hiding
    # being reversible is that someone actually reviews it.
    reported_count = (
        db.query(func.count(models.Shop.shop_id))
        .filter(models.Shop.report_count > 0).scalar()
    )
    hidden_count = (
        db.query(func.count(models.Shop.shop_id))
        .filter(models.Shop.hidden == 1).scalar()
    )
    return {
        "total_shops": shop_count,
        "total_items": item_count,
        "reported_shops": reported_count or 0,
        "hidden_shops": hidden_count or 0,
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
# Vendors
# ---------------------------------------------------------------------------
# The one management surface: every listing the food app knows about, in the
# food app's own terms. It replaced a generic shops table that showed
# shopkeeper names and phone numbers — columns this product no longer has,
# since nobody registers their own listing and numbers are never captured.

@router.get("/vendors", response_model=list[schemas.AdminVendor])
def list_vendors(
    q: str = Query("", description="Search by vendor name or address"),
    kind: str = Query("", description="Filter by food kind"),
    hidden: bool | None = Query(None, description="Only hidden, or only visible"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(models.Shop)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(models.Shop.name.ilike(pattern), models.Shop.address.ilike(pattern))
        )
    if kind:
        query = query.filter(models.Shop.food_kind == food.normalise_kind(kind))
    if hidden is not None:
        query = query.filter(models.Shop.hidden == (1 if hidden else 0))

    shops = (
        query.order_by(models.Shop.created_at.desc()).offset(skip).limit(limit).all()
    )
    return [
        {
            "shop_id": s.shop_id,
            "name": s.name,
            "food_kind": food.normalise_kind(s.food_kind),
            "kind_label": food.kind_label(s.food_kind),
            "kind_emoji": food.kind_emoji(s.food_kind),
            "address": s.address or "",
            "menu_count": len(s.items),
            "round_count": len(s.stops),
            "seen_yes": s.seen_yes or 0,
            "report_count": s.report_count or 0,
            "hidden": bool(s.hidden),
            "created_at": s.created_at,
        }
        for s in shops
    ]


@router.patch("/shops/{shop_id}", response_model=schemas.ShopOut)
def update_shop(shop_id: int, payload: schemas.ShopUpdate, db: Session = Depends(get_db)):
    """Fix a listing in place — a misread name is the common case."""
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
    """Delete one listing and everything on it.

    Uses session delete, not a bulk query delete, so the cascade actually runs
    and the menu, rounds and reports go with it.
    """
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    db.delete(shop)
    db.commit()
    embeddings.invalidate_cache()


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


@router.post("/llm/vision-test")
def llm_vision_test(payload: dict | None = None, db: Session = Depends(get_db)):
    """Prove whether a model can actually read a photo.

    Sends a freshly generated shop-board image with a random code on it and
    reports whether the model read the code back — the same job onboarding
    asks of it. Without this, picking a text-only model looks fine in the
    panel and silently breaks every photo upload."""
    model = (payload or {}).get("model") or get_default_vision_model(db)
    return vision_check.run(model, db_default=get_default_vision_model(db))


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

# ---------------------------------------------------------------------------
# Reported listings — the review queue behind the food app's flag button
# ---------------------------------------------------------------------------
# Auto-hiding is deliberately reversible and never deletes: three taps from
# strangers is enough to pull a listing out of search, but not enough to
# destroy a real vendor's entry. This is where that gets looked at.

@router.get("/reports", response_model=list[schemas.ReportedVendor])
def list_reported(hidden_only: bool = False, db: Session = Depends(get_db)):
    """Flagged listings, most-reported first."""
    query = db.query(models.Shop).filter(models.Shop.report_count > 0)
    if hidden_only:
        query = query.filter(models.Shop.hidden == 1)
    shops = query.order_by(models.Shop.report_count.desc()).all()

    out = []
    for shop in shops:
        reasons: dict[str, int] = {}
        notes: list[str] = []
        for report in shop.reports:
            reasons[report.reason] = reasons.get(report.reason, 0) + 1
            if report.note:
                notes.append(report.note)
        out.append({
            "shop_id": shop.shop_id,
            "name": shop.name,
            "kind_label": food.kind_label(shop.food_kind),
            "address": shop.address or "",
            "added_by": shop.added_by or "",
            "report_count": shop.report_count or 0,
            "hidden": bool(shop.hidden),
            "seen_yes": shop.seen_yes or 0,
            "shutdown_count": shop.shutdown_count or 0,
            "reasons": reasons,
            "notes": notes[:10],
            "created_at": shop.created_at,
        })
    return out


@router.post("/shops/{shop_id}/visibility", response_model=dict)
def set_visibility(shop_id: int, payload: dict, db: Session = Depends(get_db)):
    """Hide or restore a listing. `{"hidden": false}` clears the reports too.

    Restoring without clearing them would just re-hide the listing on the next
    stray tap, which would make the whole queue pointless.
    """
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")
    hidden = bool(payload.get("hidden"))
    shop.hidden = 1 if hidden else 0
    if not hidden:
        for report in list(shop.reports):
            db.delete(report)
        shop.report_count = 0
    db.commit()
    db.refresh(shop)
    return {"shop_id": shop.shop_id, "hidden": bool(shop.hidden),
            "report_count": shop.report_count or 0}


# ---------------------------------------------------------------------------
# Clear all data
# ---------------------------------------------------------------------------

def _wipe_everything(db: Session) -> dict:
    """Delete every shop and everything hanging off one.

    Children go first and explicitly. `db.query(Shop).delete()` is a bulk
    DELETE that never loads the rows, so SQLAlchemy's cascade rules don't run
    — and SQLite doesn't enforce foreign keys by default, so stops and reports
    for deleted shops were being left behind as orphans that nothing could
    reach or clean up. Deleting them here is what makes "clear" actually clear.
    """
    counts = {
        "reports": db.query(models.ShopReport).delete(),
        "stops": db.query(models.ShopStop).delete(),
        "items": db.query(models.Item).delete(),
        "shops": db.query(models.Shop).delete(),
    }
    db.commit()
    embeddings.invalidate_cache()
    return counts


@router.post("/data/clear", response_model=dict)
def clear_all_data(db: Session = Depends(get_db)):
    """Wipe all shops, items, rounds and reports. Settings are kept.

    AI model choices and the retention flag live in app_settings and survive
    on purpose: someone clearing test data wants an empty map, not to redo the
    setup that made the map work.
    """
    return {"cleared": True, **_wipe_everything(db)}
