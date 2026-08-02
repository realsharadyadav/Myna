from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import agent, embeddings, models, schemas
from ..database import get_db, get_default_search_model
from ..geo import haversine_km

router = APIRouter(prefix="/api/search", tags=["search"])


def _rows_for_term(db: Session, term: str, item_pool, shop_by_id):
    """Hybrid match one term (agent stage 2): substring ILIKE ∪ semantic
    cosine on stored embeddings. `item_pool`/`shop_by_id` come from a single
    pre-fetched catalogue query so per-term work stays in-memory."""
    pattern = f"%{term}%"
    like_ids = {
        it.item_id
        for it in item_pool
        if it.name and term.lower() in it.name.lower()
        or it.category and term.lower() in it.category.lower()
    }

    found: dict[int, models.Item] = {}

    # 1) Substring item/category matches
    if like_ids:
        for item in item_pool:
            if item.item_id in like_ids:
                found[item.item_id] = item

    # 2) Substring matches on shop fields -> surface those shops' items
    sql_shop_rows = (
        db.query(models.Item, models.Shop)
        .join(models.Shop, models.Item.shop_id == models.Shop.shop_id)
        .filter(
            or_(
                models.Shop.name.ilike(pattern),
                models.Shop.shopkeeper.ilike(pattern),
                models.Shop.address.ilike(pattern),
            )
        )
        .all()
    )
    for item, _shop in sql_shop_rows:
        found.setdefault(item.item_id, item)

    # 3) Semantic matches on item name/category (fixes daal/dal, kapoor/camphor).
    if embeddings.enabled():
        for item_id, _shop_id in embeddings.similar_items(db, term):
            if item_id not in found:
                for it in item_pool:
                    if it.item_id == item_id:
                        found[item_id] = it
                        break

    return [found[iid] for iid in found.keys()]


def _to_result(item, shop, lat, long, matched_term="", coverage_count=1, coverage_total=1):
    dist = haversine_km(lat, long, shop.lat, shop.long)
    return schemas.SearchResult(
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
        matched_term=matched_term,
        coverage_count=coverage_count,
        coverage_total=coverage_total,
    )


def _run_pipeline(q: str, lat: float, long: float, db: Session):
    """Agent stages 1–3: parse query -> search every item -> aggregate per shop.

    Returns (terms, method, flat_results, shop_results) where shop_results are
    already ranked by coverage (most items covered first) then distance.
    """
    terms, method = agent.parse_search_items(q, get_default_search_model(db))

    # Pre-fetch catalogue once; per-term matching (ILIKE ∪ semantic) is in-memory.
    catalogue = (
        db.query(models.Item, models.Shop)
        .join(models.Shop, models.Item.shop_id == models.Shop.shop_id)
        .all()
    )
    item_pool = [item for item, _shop in catalogue]
    shop_by_id = {shop.shop_id: shop for _item, shop in catalogue}

    flat: list[schemas.SearchResult] = []
    shops_covered: dict[int, set[str]] = {}
    per_shop_items: dict[int, list[tuple[str, object, object]]] = {}

    for term in terms:
        for item in _rows_for_term(db, term, item_pool, shop_by_id):
            shop = shop_by_id.get(item.shop_id)
            if not shop:
                continue
            shops_covered.setdefault(shop.shop_id, set()).add(term)
            per_shop_items.setdefault(shop.shop_id, []).append((term, item, shop))
            flat.append(_to_result(item, shop, lat, long, matched_term=term))

    total = len(terms)
    for r in flat:
        r.coverage_count = len(shops_covered[r.shop_id])
        r.coverage_total = total
    flat.sort(key=lambda r: (-r.coverage_count, r.distance_km))

    shop_results: list[schemas.ShopSearchResult] = []
    for shop_id, rows in per_shop_items.items():
        shop = rows[0][2]
        coverage = len(shops_covered[shop_id])
        items = [
            _to_result(item, shop, lat, long, matched_term=term,
                       coverage_count=coverage, coverage_total=total)
            for term, item, _s in rows
        ]
        items.sort(key=lambda r: (r.matched_term, r.item_name))
        shop_results.append(
            schemas.ShopSearchResult(
                shop_id=shop.shop_id,
                shop_name=shop.name,
                shopkeeper=shop.shopkeeper,
                address=shop.address,
                phone=shop.phone,
                distance_km=round(haversine_km(lat, long, shop.lat, shop.long), 2),
                coverage_count=coverage,
                coverage_total=total,
                items=items,
            )
        )
    shop_results.sort(key=lambda s: (-s.coverage_count, s.distance_km))
    return terms, method, flat, shop_results


@router.get("", response_model=list[schemas.SearchResult])
def search(
    q: str = Query(..., min_length=1),
    lat: float = Query(...),
    long: float = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Agentic search pipeline: the query is parsed into individual items
    ("salt milk and mango" -> salt/milk/mango), every item is matched across
    the catalogue, and hits are grouped per shop — shops covering more of
    your list rank first, then nearest first."""
    _terms, _method, flat, _shops = _run_pipeline(q, lat, long, db)
    return flat[:limit]


@router.get("/shops", response_model=schemas.AgentSearchResponse)
def search_shops(
    q: str = Query(..., min_length=1),
    lat: float = Query(...),
    long: float = Query(...),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Same pipeline, returned as one card per shop with the matching items
    inside and a coverage score (e.g. "2/3 items here")."""
    terms, method, _flat, shop_results = _run_pipeline(q, lat, long, db)
    return schemas.AgentSearchResponse(
        query=q, items=terms, method=method, shops=shop_results[:limit]
    )


@router.get("/one-tap", response_model=schemas.OneTapSearchResponse)
def search_one_tap(
    q: str = Query(..., min_length=1),
    lat: float = Query(...),
    long: float = Query(...),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """One-tap search: full pipeline plus a ready shopping list — one
    representative product per requested item, picked from the nearest shop
    that stocks it."""
    terms, method, _flat, shop_results = _run_pipeline(q, lat, long, db)

    best: dict[str, schemas.SearchResult] = {}
    for shop in shop_results:  # already ranked coverage desc, then nearest
        for r in shop.items:
            if r.matched_term not in best:
                best[r.matched_term] = r

    shopping_list = [
        schemas.ShoppingListItem(
            item=term,
            product=r.item_name if r else term,
            category=r.item_category if r else "",
            photo_url=r.item_photo_url if r else "",
            shop_id=r.shop_id if r else 0,
            shop_name=r.shop_name if r else "",
            distance_km=r.distance_km if r else 0.0,
            in_stock=r is not None,
        )
        for term in terms
        for r in [best.get(term)]
    ]

    return schemas.OneTapSearchResponse(
        query=q,
        items=terms,
        method=method,
        shopping_list=shopping_list,
        shops=shop_results[:limit],
    )
