"""The food app: one-photo add, "paas me kya mil raha hai", freshness votes.

Three ideas hold this together, and each one exists to kill a specific reason
hyperlocal directories die:

1. **Anyone can add anyone.** A listing is not owned by the vendor, so the app
   doesn't need a thela-wala to download anything before it has data. There is
   no login here on purpose — an anonymous device id is enough to attribute a
   listing and to stop one person voting on the same cart all day.

2. **One photo is the whole add flow.** A street-food board *is* the menu and
   the price list, so `ai.read_food_board` gets the name, the kind and every
   dish out of a single frame. Everything after that is editable, nothing is
   mandatory.

3. **The street keeps the data fresh, not the vendor.** Vendors never update
   their own listings. Passers-by tapping "haan, hai" / "nahi mila" do, and
   `trust` turns those taps into how confidently a card is shown.

Phone numbers are deliberately never captured by the add flow: someone can list
a cart they walked past, but they can't publish that vendor's number without
them. A vendor claiming their own listing later is what unlocks that field.
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, embeddings, food, models, schedule, schemas
from ..database import get_db, get_default_vision_model, get_retain_uploaded_images
from ..geo import haversine_km, reverse_geocode
from ..storage import save_upload

router = APIRouter(prefix="/api/food", tags=["food"])

# How far "paas me" means by default. A thela is a walk, not a drive.
DEFAULT_RADIUS_KM = 3.0
MAX_RADIUS_KM = 25.0

# A listing nobody has confirmed in this long is shown as stale rather than
# hidden — a cart that moved is still a useful lead about where food is.
FRESH_DAYS = 2
STALE_DAYS = 14


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def _seen_text(shop: models.Shop, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    if not shop.last_seen_at:
        return "Abhi tak kisi ne confirm nahi kiya"
    days = (now - shop.last_seen_at).days
    if days <= 0:
        return "Aaj dekha gaya"
    if days == 1:
        return "Kal dekha gaya"
    if days < 7:
        return f"{days} din pehle dekha gaya"
    if days < 30:
        return f"{days // 7} hafte pehle dekha gaya"
    return "Kaafi purana"


def _trust(shop: models.Shop, now: datetime | None = None) -> str:
    """How much to believe this listing, as one word the UI can style on.

    'doubtful' is the only one that changes ranking: more people saying "nahi
    mila" than "haan hai" means the cart has almost certainly moved on, and
    showing it first would burn the exact trust the votes are there to build.
    """
    now = now or datetime.utcnow()
    if shop.seen_no > shop.seen_yes and shop.seen_no >= 2:
        return "doubtful"
    if not shop.last_seen_at:
        return "new"
    days = (now - shop.last_seen_at).days
    if days <= FRESH_DAYS:
        return "fresh"
    if days <= STALE_DAYS:
        return "ok"
    return "stale"


# ---------------------------------------------------------------------------
# Card building
# ---------------------------------------------------------------------------

def _best_stop(shop: models.Shop, lat: float | None, long: float | None) -> dict | None:
    """The stop that answers "where do I go right now".

    Sorted the same way search ranks: standing here now beats later today beats
    another day, and only within a bucket does distance decide. A cart that's
    out right now two streets away is a better answer than one that parks
    outside your gate on Friday.
    """
    if not shop.stops:
        return None
    views = []
    for stop in shop.stops:
        view = schedule.stop_view(stop)
        if lat is not None and long is not None:
            view["distance_km"] = round(haversine_km(lat, long, stop.lat, stop.long), 2)
        views.append(view)
    views.sort(key=lambda v: (v["rank"], v.get("distance_km") if v.get("distance_km") is not None else 0))
    return views[0]


def _all_stops(shop: models.Shop, lat: float | None, long: float | None) -> list[dict]:
    views = []
    for stop in shop.stops:
        view = schedule.stop_view(stop)
        if lat is not None and long is not None:
            view["distance_km"] = round(haversine_km(lat, long, stop.lat, stop.long), 2)
        views.append(view)
    views.sort(key=lambda v: (v["rank"], v["start_time"] or "99:99"))
    return views


def vendor_view(
    shop: models.Shop,
    lat: float | None = None,
    long: float | None = None,
    matched: list[str] | None = None,
) -> dict:
    """One shop → one card. The only shape the food UI ever renders."""
    stops = _all_stops(shop, lat, long)
    best = _best_stop(shop, lat, long)

    # A moving vendor is found at its stop, not at wherever it happened to be
    # registered, so the card's coordinates (and its Directions link) follow the
    # stop when there is one.
    if best:
        card_lat, card_long = best["lat"], best["long"]
        open_text = best["status_text"]
        is_open = best["status"] == "here_now"
    else:
        card_lat, card_long = shop.lat, shop.long
        open_text, is_open = "", False

    distance = (
        round(haversine_km(lat, long, card_lat, card_long), 2)
        if lat is not None and long is not None
        else 0.0
    )

    return {
        "shop_id": shop.shop_id,
        "name": shop.name,
        "food_kind": food.normalise_kind(shop.food_kind),
        "kind_label": food.kind_label(shop.food_kind),
        "kind_emoji": food.kind_emoji(shop.food_kind),
        "address": shop.address or "",
        "phone": shop.phone or "",
        "photo_url": shop.photo_url or "",
        "lat": card_lat,
        "long": card_long,
        "distance_km": distance,
        "shop_type": shop.shop_type or "fixed",
        "stop": best,
        "stops": stops,
        "open_text": open_text,
        "is_open_now": is_open,
        "menu": [
            {
                "item_id": item.item_id,
                "name": item.name,
                "category": item.category or "",
                "price": item.price or 0.0,
            }
            for item in shop.items
        ],
        "matched": matched or [],
        "seen_text": _seen_text(shop),
        "seen_yes": shop.seen_yes or 0,
        "seen_no": shop.seen_no or 0,
        "trust": _trust(shop),
    }


# ---------------------------------------------------------------------------
# Reference data for the UI
# ---------------------------------------------------------------------------

@router.get("/kinds", response_model=dict)
def list_kinds():
    """Vendor kinds and the popular-dish chips, so the client hardcodes neither."""
    return {"kinds": food.kind_list(), "popular": food.POPULAR,
            "categories": food.CATEGORY_NAMES}


# ---------------------------------------------------------------------------
# One-photo add
# ---------------------------------------------------------------------------

@router.post("/add", response_model=schemas.QuickAddResponse)
def quick_add(
    photo: UploadFile = File(...),
    lat: float = Form(...),
    long: float = Form(...),
    address: str = Form(""),
    name: str = Form(""),
    kind: str = Form(""),
    device_id: str = Form(""),
    # Optional, and only meaningful for a moving thela. Left blank the vendor is
    # simply listed at this spot — asking someone to fill a timetable for a cart
    # they walked past is how you lose them on the add screen.
    day_of_week: int = Form(schedule.EVERY_DAY),
    start_time: str = Form(""),
    end_time: str = Form(""),
    db: Session = Depends(get_db),
):
    """Photo + GPS → a listed vendor with its whole menu. That's the flow.

    `name` and `kind` are accepted as overrides for the retry case (the photo
    was unreadable, so the user typed a name); normally both come out of the
    photo.
    """
    retain = get_retain_uploaded_images(db)
    local_path, public_url = save_upload(photo, retain=retain)
    vision_model = get_default_vision_model(db)
    try:
        board, error = ai.read_food_board(local_path, model=vision_model)
    finally:
        if not retain:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass

    final_name = (name or "").strip() or board["name"]
    if not final_name and not board["items"]:
        # Nothing readable and nothing typed — there is no listing to make.
        return {"created": False, "vendor": None, "read_name": "", "read_kind": "",
                "item_count": 0, "error": error or "Naam nahi mila. Naam type karke dobara try karo."}

    final_kind = food.normalise_kind(kind or board["kind"])
    if not final_name:
        # A menu with no legible board still deserves a listing; name it after
        # what it sells rather than bouncing the user back to a form.
        final_name = f"{board['items'][0]['name']} wala"

    shop = models.Shop(
        name=final_name,
        shopkeeper="",
        lat=lat,
        long=long,
        address=(address or "").strip() or reverse_geocode(lat, long),
        phone="",
        photo_url=public_url if retain else "",
        shop_type="mobile" if food.is_mobile_kind(final_kind) else "fixed",
        food_kind=final_kind,
        added_by=(device_id or "").strip(),
        # Whoever adds a vendor has just seen it, so the listing starts fresh
        # instead of starting life as unconfirmed.
        seen_yes=1,
        seen_no=0,
        last_seen_at=datetime.utcnow(),
    )
    db.add(shop)
    db.flush()

    items = [
        models.Item(
            shop_id=shop.shop_id,
            name=entry["name"],
            category=entry["category"],
            price=entry.get("price") or 0.0,
        )
        for entry in board["items"]
    ]
    if items:
        embeddings.embed_items(items, db)
        db.add_all(items)

    # Timings turn this into a proper round; without them the cart is simply
    # listed where it was photographed.
    if start_time or end_time or day_of_week != schedule.EVERY_DAY:
        db.add(models.ShopStop(
            shop_id=shop.shop_id,
            label="",
            lat=lat,
            long=long,
            address=shop.address,
            day_of_week=day_of_week,
            start_time=start_time or "",
            end_time=end_time or "",
        ))
        shop.shop_type = "mobile"

    db.commit()
    db.refresh(shop)
    embeddings.invalidate_cache()

    return {
        "created": True,
        "vendor": vendor_view(shop, lat, long),
        "read_name": board["name"],
        "read_kind": board["kind"],
        "item_count": len(items),
        # A partial read is still a success — the caller shows this as a nudge
        # ("menu nahi padha, khud add karo"), not as a failure.
        "error": error if not items else "",
    }


# ---------------------------------------------------------------------------
# Browse / search: "paas me kya mil raha hai"
# ---------------------------------------------------------------------------

def _matches(shop: models.Shop, terms: list[str]) -> list[str]:
    """Which of the searched words this vendor answers.

    Matched against the menu, the vendor's name and its kind together, so
    "momos" finds both a cart with Momos on the board and one called Momo
    Point that never listed an item.
    """
    if not terms:
        return []
    haystack = " ".join(
        [shop.name or "", food.kind_label(shop.food_kind)]
        + [f"{i.name} {i.category}" for i in shop.items]
    ).lower()
    return [term for term in terms if term in haystack]


@router.get("/near", response_model=schemas.NearResponse)
def near(
    lat: float,
    long: float,
    q: str = "",
    kind: str = "",
    radius_km: float = DEFAULT_RADIUS_KM,
    open_now: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """The home screen. No query = everything nearby; a query filters it.

    Ranking is "what can I actually eat right now": open beats closed, a
    doubtful listing sinks, and only then does distance decide. Sorting purely
    by distance would put a cart that comes on Sundays above one standing at the
    corner, which is the wrong answer to the only question being asked.
    """
    radius = max(0.1, min(radius_km or DEFAULT_RADIUS_KM, MAX_RADIUS_KM))
    terms = [t for t in (q or "").lower().replace(",", " ").split() if len(t) > 1]
    wanted_kind = food.normalise_kind(kind) if kind else ""

    cards = []
    for shop in db.query(models.Shop).all():
        if wanted_kind and food.normalise_kind(shop.food_kind) != wanted_kind:
            continue
        matched = _matches(shop, terms)
        if terms and not matched:
            continue
        card = vendor_view(shop, lat, long, matched)
        if card["distance_km"] > radius:
            continue
        if open_now and not card["is_open_now"]:
            continue
        cards.append(card)

    cards.sort(key=lambda c: (
        0 if c["is_open_now"] else 1,
        1 if c["trust"] == "doubtful" else 0,
        -len(c["matched"]),
        c["distance_km"],
    ))
    return {"query": q, "count": len(cards), "vendors": cards[:limit]}


@router.get("/{shop_id}", response_model=schemas.FoodVendorOut)
def get_vendor(shop_id: int, lat: float | None = None, long: float | None = None,
               db: Session = Depends(get_db)):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Ye dukaan nahi mili")
    return vendor_view(shop, lat, long)


# ---------------------------------------------------------------------------
# "Abhi bhi yahan hai?" — the freshness loop
# ---------------------------------------------------------------------------

@router.post("/{shop_id}/seen", response_model=schemas.FoodVendorOut)
def report_seen(shop_id: int, payload: schemas.SeenReport, db: Session = Depends(get_db)):
    """One tap from a passer-by. This is what keeps the data alive.

    A "haan" also moves `last_seen_at`; a "nahi" doesn't, because a cart being
    missing is not evidence about when it was last there — it only argues the
    listing is wrong, which is what `seen_no` already carries.
    """
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Ye dukaan nahi mili")
    if payload.yes:
        shop.seen_yes = (shop.seen_yes or 0) + 1
        shop.last_seen_at = datetime.utcnow()
    else:
        shop.seen_no = (shop.seen_no or 0) + 1
    db.commit()
    db.refresh(shop)
    return vendor_view(shop)


@router.post("/{shop_id}/items", response_model=schemas.MenuItemOut)
def add_menu_item(shop_id: int, payload: schemas.ItemCreate, db: Session = Depends(get_db)):
    """Add one dish by hand — the escape hatch when the board wasn't readable."""
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Ye dukaan nahi mili")
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Dish ka naam chahiye")
    item = models.Item(
        shop_id=shop_id,
        name=name,
        category=food.normalise_category(payload.category, name),
        price=payload.price or 0.0,
    )
    embeddings.embed_item(item, db)
    db.add(item)
    db.commit()
    db.refresh(item)
    embeddings.invalidate_cache()
    return {"item_id": item.item_id, "name": item.name,
            "category": item.category, "price": item.price or 0.0}
