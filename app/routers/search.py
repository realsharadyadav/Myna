from fastapi import APIRouter, Depends, Query
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
    range_km: float = Query(5.0, gt=0, le=50),
    db: Session = Depends(get_db),
):
    """Find items matching `q` at shops within `range_km` of (lat, long), nearest first."""
    pattern = f"%{q.strip()}%"
    rows = (
        db.query(models.Item, models.Shop)
        .join(models.Shop, models.Item.shop_id == models.Shop.shop_id)
        .filter(models.Item.name.ilike(pattern))
        .all()
    )

    results = []
    for item, shop in rows:
        dist = haversine_km(lat, long, shop.lat, shop.long)
        if dist <= range_km:
            results.append(
                schemas.SearchResult(
                    shop_id=shop.shop_id,
                    shop_name=shop.name,
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
    return results
