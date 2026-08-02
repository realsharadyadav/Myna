from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import ai, models, schemas
from ..database import get_db

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
            models.Shop.name.ilike(pattern) | models.Shop.address.ilike(pattern)
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


@router.patch("/items/{item_id}", response_model=schemas.ItemOut)
def update_any_item(item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
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
    """Which providers have keys configured and which model is default."""
    return {
        "providers": ai.list_models(),
        "default_model": ai.get_default_model(),
        "configured_providers": ai.configured_providers(),
    }
