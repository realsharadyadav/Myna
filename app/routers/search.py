from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..geo import haversine_km

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[schemas.SearchResult])
def search(
    q: str = Query(..., min_length=1),
    lat: float = Query(...),
    long: float = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Find items matching `q` across item name, item category, shop name,
    shopkeeper name and shop address, nearest first (no range filter)."""
    pattern = f"%{q.strip()}%"
    rows = (
        db.query(models.Item, models.Shop)
        .join(models.Shop, models.Item.shop_id == models.Shop.shop_id)
        .filter(
            or_(
                models.Item.name.ilike(pattern),
                models.Item.category.ilike(pattern),
                models.Shop.name.ilike(pattern),
                models.Shop.shopkeeper.ilike(pattern),
                models.Shop.address.ilike(pattern),
            )
        )
        .all()
    )

    results = []
    for item, shop in rows:
        dist = haversine_km(lat, long, shop.lat, shop.long)
        results.append(
            schemas.SearchResult(
                shop_id=shop.shop_id,
                shop_name=shop.name,
                shopkeeper=shop.shopkeeper,
                address=shop.address,
                phone=shop.phone,
                distance_km=round(dist, 2),
                item_id=item.item_id,
                item_name=item.name,
                item_category=item.category,
                item_photo_url=item.photo_url,
            )
        )
    results.sort(key=lambda r: r.distance_km)
    return results[:limit]
