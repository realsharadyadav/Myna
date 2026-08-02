import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import agent, dishes, embeddings, models, schedule, schemas, synonyms
from ..database import get_db, get_default_search_model
from ..geo import haversine_km

router = APIRouter(prefix="/api/search", tags=["search"])


def _matches_alias(text: str, aliases: set[str]) -> bool:
    """Word-aware substring match: an alias has to start a word, and may only
    be followed by a plural suffix.

    A plain `alias in text` check reads far too loosely on real catalogues —
    "haldi" (turmeric) matched "Haldiram Bhujia", which looks especially bad in
    dish mode where every ingredient is searched at once. Anchoring at a word
    start still allows the matches that matter ("parle" -> "Parle-G Gold",
    "atta" -> "Aashirvaad Atta 5kg") and keeps simple plurals ("onion" ->
    "Onions 1kg", "chilli" -> "Chillies")."""
    if not text:
        return False
    lowered = text.lower()
    return any(
        re.search(rf"\b{re.escape(alias)}(?:s|es)?\b", lowered)
        for alias in aliases
        if alias
    )


def _rows_for_term(db: Session, term: str, item_pool, shop_by_id):
    """Hybrid match one term (agent stage 2): substring ILIKE ∪ synonym
    glossary ∪ semantic cosine on stored embeddings. `item_pool`/`shop_by_id`
    come from a single pre-fetched catalogue query so per-term work stays
    in-memory."""
    pattern = f"%{term}%"
    aliases = synonyms.expand(term.lower())
    like_ids = {
        it.item_id
        for it in item_pool
        if _matches_alias(it.name, aliases) or _matches_alias(it.category, aliases)
    }

    found: dict[int, models.Item] = {}

    # 1) Substring item/category matches, including known synonyms/aliases
    # (e.g. "daal" -> also try "dal"/"dhal"; "kapoor" -> also try "camphor").
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

    # 3) Semantic matches on item name/category — broader coverage beyond the
    # curated glossary above (e.g. "milk" ~ "dairy").
    if embeddings.enabled():
        for item_id, _shop_id in embeddings.similar_items(db, term):
            if item_id not in found:
                for it in item_pool:
                    if it.item_id == item_id:
                        found[item_id] = it
                        break

    return [found[iid] for iid in found.keys()]


def _stop_views(shop, lat, long):
    """Rank a mobile vendor's stops for this customer.

    A thela has no address to walk to — it has rounds. The stop we point the
    customer at is the one they can actually meet: a stop the vendor is
    standing at right now wins, otherwise the soonest round, nearest first
    within each bucket. The rest travel along on the card so "or Friday in
    Gali 9, 400 m away" is still visible.
    """
    views = []
    for s in shop.stops:
        view = schedule.stop_view(s)
        view["distance_km"] = round(haversine_km(lat, long, s.lat, s.long), 2)
        views.append(view)
    views.sort(key=lambda v: (v["rank"], v["distance_km"]))
    return views


def _shop_position(shop, lat, long, stop):
    """Where this shop *is*, for distance and directions: its address for a
    fixed shop, the matched stop for a cart."""
    if stop:
        return stop["lat"], stop["long"], stop["distance_km"]
    return shop.lat, shop.long, round(haversine_km(lat, long, shop.lat, shop.long), 2)


def _to_result(item, shop, lat, long, matched_term="", coverage_count=1, coverage_total=1, stop=None):
    shop_lat, shop_long, dist = _shop_position(shop, lat, long, stop)
    return schemas.SearchResult(
        shop_id=shop.shop_id,
        shop_name=shop.name,
        shopkeeper=shop.shopkeeper,
        address=(stop["label"] or stop["address"]) if stop else shop.address,
        phone=shop.phone,
        shop_lat=shop_lat,
        shop_long=shop_long,
        distance_km=dist,
        shop_type=shop.shop_type or "fixed",
        stop=schemas.StopOut(**stop) if stop else None,
        item_id=item.item_id,
        item_name=item.name,
        item_category=item.category,
        item_photo_url=item.photo_url,
        matched_term=matched_term,
        coverage_count=coverage_count,
        coverage_total=coverage_total,
    )


def _run_pipeline(q: str, lat: float, long: float, db: Session, mode: str = ""):
    """Agent stages 1–3: parse query -> search every item -> aggregate per shop.

    Returns (terms, method, flat_results, shop_results) where shop_results are
    already ranked by coverage (most items covered first) then distance.
    """
    terms, method = agent.parse_search_items(q, get_default_search_model(db), mode=mode)

    # Pre-fetch catalogue once; per-term matching (ILIKE ∪ semantic) is in-memory.
    catalogue = (
        db.query(models.Item, models.Shop)
        .join(models.Shop, models.Item.shop_id == models.Shop.shop_id)
        .all()
    )
    item_pool = [item for item, _shop in catalogue]
    shop_by_id = {shop.shop_id: shop for _item, shop in catalogue}
    # Stops are ranked once per shop, not once per matched item.
    stops_by_shop = {
        sid: _stop_views(shop, lat, long)
        for sid, shop in shop_by_id.items()
        if shop.shop_type == "mobile"
    }
    best_stop = {sid: views[0] for sid, views in stops_by_shop.items() if views}

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
            flat.append(_to_result(item, shop, lat, long, matched_term=term,
                                   stop=best_stop.get(shop.shop_id)))

    total = len(terms)
    for r in flat:
        r.coverage_count = len(shops_covered[r.shop_id])
        r.coverage_total = total
    flat.sort(key=lambda r: (-r.coverage_count, _availability_rank(r.stop), r.distance_km))

    shop_results: list[schemas.ShopSearchResult] = []
    for shop_id, rows in per_shop_items.items():
        shop = rows[0][2]
        coverage = len(shops_covered[shop_id])
        stop = best_stop.get(shop_id)
        items = [
            _to_result(item, shop, lat, long, matched_term=term,
                       coverage_count=coverage, coverage_total=total, stop=stop)
            for term, item, _s in rows
        ]
        items.sort(key=lambda r: (r.matched_term, r.item_name))
        shop_lat, shop_long, dist = _shop_position(shop, lat, long, stop)
        shop_results.append(
            schemas.ShopSearchResult(
                shop_id=shop.shop_id,
                shop_name=shop.name,
                shopkeeper=shop.shopkeeper,
                address=(stop["label"] or stop["address"]) if stop else shop.address,
                phone=shop.phone,
                shop_lat=shop_lat,
                shop_long=shop_long,
                distance_km=dist,
                coverage_count=coverage,
                coverage_total=total,
                shop_type=shop.shop_type or "fixed",
                stop=schemas.StopOut(**stop) if stop else None,
                stops=[schemas.StopOut(**v) for v in stops_by_shop.get(shop_id, [])],
                items=items,
            )
        )
    # Coverage first (unchanged), then what you can buy right now: fixed shops
    # and carts standing at their stop, then today's rounds, then later in the
    # week — nearest first inside each group.
    shop_results.sort(key=lambda s: (-s.coverage_count, _availability_rank(s.stop), s.distance_km))
    return terms, method, flat, shop_results


def _availability_rank(stop) -> int:
    """0 for anything you can reach now (a fixed shop, or a cart at its stop),
    1 for a round later today, 2 for another day."""
    return stop.rank if stop is not None else schedule.AVAILABLE_NOW


@router.get("/dishes", response_model=dict)
def popular_dishes(limit: int = Query(12, ge=1, le=40)):
    """Dish suggestions for the app's dish-mode chips, so the frontend doesn't
    keep its own copy of the list."""
    return {"dishes": dishes.popular(limit)}


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
    mode: str = Query("", description="'dish' expands a dish name into its ingredients first"),
    db: Session = Depends(get_db),
):
    """Same pipeline, returned as one card per shop with the matching items
    inside and a coverage score (e.g. "2/3 items here")."""
    terms, method, _flat, shop_results = _run_pipeline(q, lat, long, db, mode=mode)
    return schemas.AgentSearchResponse(
        query=q, items=terms, method=method, shops=shop_results[:limit]
    )


@router.get("/one-tap", response_model=schemas.OneTapSearchResponse)
def search_one_tap(
    q: str = Query(..., min_length=1),
    lat: float = Query(...),
    long: float = Query(...),
    limit: int = Query(10, ge=1, le=50),
    mode: str = Query("", description="'dish' expands a dish name into its ingredients first"),
    db: Session = Depends(get_db),
):
    """One-tap search: full pipeline plus a ready shopping list — one
    representative product per requested item, picked from the nearest shop
    that stocks it. With mode='dish' the query is a dish name and the
    shopping list is its ingredients."""
    terms, method, _flat, shop_results = _run_pipeline(q, lat, long, db, mode=mode)

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
            shop_type=r.shop_type if r else "fixed",
            availability=r.stop.status_text if (r and r.stop) else "",
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
