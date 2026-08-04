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
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai, embeddings, food, models, schedule, schemas
from ..database import (
    get_db,
    get_default_search_model,
    get_default_vision_model,
    get_retain_uploaded_images,
)
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

def _is_closed_today(shop: models.Shop) -> bool:
    """Did someone report this shut *today*?

    Compared in the vendor's local timezone, not UTC — a "aaj band hai" tapped
    at 9 PM IST is about that Tuesday, and comparing UTC dates would quietly
    carry it into the next morning.
    """
    if not shop.closed_today_at:
        return False
    local = shop.closed_today_at.replace(tzinfo=timezone.utc).astimezone(schedule.tz())
    return local.date() == schedule.now_local().date()


def _wrongness(shop: models.Shop) -> int:
    """How much the votes argue this listing is *wrong* about where the vendor is.

    Weighted per reason (food.SEEN_REASONS): "aaj band hai" contributes zero,
    because a vendor's day off says nothing about whether the listing is right.
    """
    return (
        (shop.seen_no or 0) * food.SEEN_REASONS["unknown"]["weight"]
        + (shop.moved_count or 0) * food.SEEN_REASONS["moved"]["weight"]
        + (shop.shutdown_count or 0) * food.SEEN_REASONS["shut_down"]["weight"]
    )


def _seen_text(shop: models.Shop, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    # Today's status is the more useful sentence, and it says nothing bad about
    # the listing itself.
    if _is_closed_today(shop):
        return "Aaj band bataya gaya"
    if (shop.shutdown_count or 0) >= 2 and shop.shutdown_count > (shop.seen_yes or 0):
        return "Log keh rahe hain ab lagta hi nahi"
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

    Only two values change ranking. 'closed' means enough people said the
    vendor is gone for good, and it drops out of search entirely. 'doubtful'
    means the weighted votes say this spot is wrong — note that a listing
    reported shut *today* is neither, which is the whole point of asking why:
    a chaat wala closed for one Tuesday would otherwise be voted down by
    exactly the people who like him most.
    """
    now = now or datetime.utcnow()
    if (shop.shutdown_count or 0) >= 2 and shop.shutdown_count > (shop.seen_yes or 0):
        return "closed"
    wrongness = _wrongness(shop)
    if wrongness >= 2 and wrongness > (shop.seen_yes or 0):
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
        "closed_today": _is_closed_today(shop),
        "moved_count": shop.moved_count or 0,
        "shutdown_count": shop.shutdown_count or 0,
        "report_count": shop.report_count or 0,
        "hidden": bool(shop.hidden),
    }


# ---------------------------------------------------------------------------
# Reference data for the UI
# ---------------------------------------------------------------------------

@router.get("/health", response_model=dict)
def health():
    """Cheap liveness probe, used to tell two failures apart in the client.

    "Search failed" reads the same whether the network is down or the page is
    pointed at a host that has no API — which is exactly what happened when a
    separately deployed front end carried the wrong backend URL: every request
    failed while both services reported healthy. The client probes this on
    failure so it can name the real problem instead of blaming the user's net.
    """
    return {"ok": True, "app": "myna"}


@router.get("/kinds", response_model=dict)
def list_kinds():
    """Vendor kinds, chips and the reason lists, so the client hardcodes none."""
    return {
        "kinds": food.kind_list(),
        "popular": food.POPULAR,
        "categories": food.CATEGORY_NAMES,
        "seen_reasons": food.seen_reason_list(),
        "report_reasons": food.report_reason_list(),
    }


# ---------------------------------------------------------------------------
# Photo add
# ---------------------------------------------------------------------------
# Every extra photo is another vision call, so the count is capped: five is
# well past the point where a thela has anything new to show, and it bounds
# both the bill and how long someone stands on a footpath waiting.
MAX_PHOTOS = 5


@router.post("/add", response_model=schemas.QuickAddResponse)
def quick_add(
    # Repeated `photos` is the real field; `photo` stays as a single-file alias
    # so anything built against the one-photo version keeps working.
    photos: list[UploadFile] = File(default=[]),
    photo: UploadFile | None = File(default=None),
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
    """Photos + GPS → a listed vendor with its whole menu. That's the flow.

    One photo is enough, but more is better and they're merged: a wide shot
    carries the signboard name, a close one carries the rates, a shot of the
    tawa carries dishes nobody wrote down. The first photo is treated as the
    board — its name wins — which is what the add screen asks for.

    `name` and `kind` are accepted as overrides for the retry case (the board
    was unreadable, so the user typed a name); normally both come out of the
    photos.
    """
    uploads = [f for f in ([*photos, photo] if photo else list(photos)) if f is not None]
    if not uploads:
        raise HTTPException(422, "Kam se kam ek photo chahiye")
    uploads = uploads[:MAX_PHOTOS]

    retain = get_retain_uploaded_images(db)
    saved = [save_upload(f, retain=retain) for f in uploads]
    local_paths = [path for path, _ in saved]
    # The first photo is the one shown on the card, so it's the one kept.
    public_url = saved[0][1]
    vision_model = get_default_vision_model(db)
    try:
        board, error = ai.read_food_boards(local_paths, model=vision_model)
    finally:
        # Only the card's photo is worth keeping even when retention is on —
        # the rest were read for their text and have done their job.
        for index, path in enumerate(local_paths):
            if retain and index == 0:
                continue
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    final_name = (name or "").strip() or board["name"]
    if not final_name and not board["items"]:
        # Nothing readable and nothing typed — there is no listing to make.
        return {"created": False, "vendor": None, "read_name": "", "read_kind": "",
                "item_count": 0, "photo_count": len(uploads),
                "error": error or "Naam nahi mila. Naam type karke dobara try karo."}

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
        "photo_count": len(uploads),
        # A partial read is still a success — the caller shows this as a nudge
        # ("menu nahi padha, khud add karo"), not as a failure.
        "error": error if not items else "",
    }


# ---------------------------------------------------------------------------
# Browse / search: "paas me kya mil raha hai"
# ---------------------------------------------------------------------------

def term_in(term: str, haystack: str) -> bool:
    """Word-aware substring match.

    A plain `in` check is wrong here in a way that is easy to miss: "tea"
    appears inside "Steam Momos", so searching for tea returned a momos cart.
    Anchoring to a word start keeps the useful case — "momo" still matches
    "Momos", "samosa" matches "Samosas" — while refusing matches that begin
    mid-word.
    """
    if not term:
        return False
    return re.search(r"\b" + re.escape(term), haystack) is not None


def _haystack(shop: models.Shop) -> str:
    """The text a search term is matched against.

    Menu, vendor name and kind together, so "momos" finds both a cart with
    Momos on the board and one called Momo Point that never listed an item.
    """
    return " ".join(
        [shop.name or "", food.kind_label(shop.food_kind)]
        + [f"{i.name} {i.category}" for i in shop.items]
    ).lower()


def _menu_vocabulary(db: Session) -> set[str]:
    """Dish words actually on menus, so spelling correction can aim at them.

    A vendor selling something the built-in list never heard of should still
    be findable when the customer misspells it.
    """
    words: set[str] = set()
    for (name,) in db.query(models.Item.name).distinct():
        cleaned = (name or "").lower().strip()
        if cleaned:
            words.add(cleaned)
            words.update(w for w in cleaned.split() if len(w) > 3)
    return words


def resolve_terms(db: Session, terms: list[str]) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Each searched word → every spelling worth matching it on, plus the
    spelling corrections worth telling the user about.

    Three stages, cheapest first, because most searches never need the
    expensive one:

    1. The word itself, always.
    2. Fuzzy correction against the dish vocabulary plus the menus actually
       nearby — free, instant, and enough for "chawmin" → "chowmein".
    3. Known other names for the same food (food.SYNONYMS), which is what makes
       "dumpling" find a Momos board. Spelling correction can't do this — those
       words aren't misspellings of each other, they share no letters.
    4. An LLM, but *only* for words the first three couldn't place. Paying for
       a model call on every search would be waste when "momos" needs no help.
    """
    if not terms:
        return {}, {}

    known = food.vocabulary(_menu_vocabulary(db))
    resolved = {term: {term} for term in terms}
    # Only *spelling* fixes go here. Synonyms widen the search silently and on
    # purpose: telling someone "dimsum dikha rahe hain momos ke liye" when they
    # spelled momos perfectly is noise, not transparency.
    corrections: dict[str, str] = {}

    unresolved = []
    for term in terms:
        fixed = food.correct_term(term, known)
        if fixed != term:
            resolved[term].add(fixed)
            corrections[term] = food.canonical(fixed)
        elif term not in known and not any(term in word for word in known):
            unresolved.append(term)
        # Other names for the same food, for the term and its corrected form
        # alike — "dumpling" and "momoz" should both reach a Momos board.
        for variant in list(resolved[term]):
            resolved[term].update(food.synonyms_of(variant))

    if unresolved:
        for typed, fixed in ai.correct_food_query(
            unresolved, sorted(known), model=get_default_search_model(db)
        ).items():
            resolved.setdefault(typed, {typed}).add(fixed)
            resolved[typed].update(food.synonyms_of(fixed))
            corrections[typed] = food.canonical(fixed)
    return resolved, corrections


def semantic_hits(db: Session, terms: list[str]) -> dict[str, set[int]]:
    """Each searched word → vendors whose menu *means* the same thing.

    This is what the stored item embeddings are for. Substring matching can't
    connect "momos" to a menu that only says "Dimsum", and no amount of
    spelling correction will either — the words simply aren't alike. Cosine
    similarity is.
    """
    hits: dict[str, set[int]] = {}
    # Skipped entirely when the active backend is the hashing fallback — those
    # vectors carry no meaning, and matching on them invents results.
    if not terms or not embeddings.semantic_ready(db):
        return hits
    for term in terms:
        try:
            found = embeddings.similar_items(db, term)
        except Exception:
            # Semantic search is an enhancement, never a hard dependency — a
            # broken embedding backend must not take the whole search down.
            continue
        if found:
            hits[term] = {shop_id for _item_id, shop_id in found}
    return hits


def _matches(shop: models.Shop, terms: list[str],
             resolved: dict[str, set[str]] | None = None,
             semantic: dict[str, set[int]] | None = None) -> list[str]:
    """Which of the searched words this vendor answers.

    Reported per *original* word, so a two-dish search reads correctly: ask
    for "momos aur chawmin" and the momos cart comes back matching "momos"
    while the chowmein cart matches "chawmin", each shown for its own reason.
    """
    if not terms:
        return []
    resolved = resolved or {t: {t} for t in terms}
    semantic = semantic or {}
    haystack = _haystack(shop)
    matched = []
    for term in terms:
        variants = resolved.get(term, {term})
        if any(term_in(variant, haystack) for variant in variants):
            matched.append(term)
        elif shop.shop_id in semantic.get(term, ()):
            matched.append(term)
    return matched


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
    terms = food.split_query(q)
    resolved, corrections = resolve_terms(db, terms)
    semantic = semantic_hits(db, terms)
    wanted_kind = food.normalise_kind(kind) if kind else ""

    cards = []
    for shop in db.query(models.Shop).all():
        # Reported into hiding, or voted permanently shut — neither belongs in
        # a "where do I eat now" list. Both are reversible states, not deletes.
        if shop.hidden:
            continue
        if wanted_kind and food.normalise_kind(shop.food_kind) != wanted_kind:
            continue
        matched = _matches(shop, terms, resolved, semantic)
        if terms and not matched:
            continue
        card = vendor_view(shop, lat, long, matched)
        if card["trust"] == "closed":
            continue
        if card["distance_km"] > radius:
            continue
        if open_now and not card["is_open_now"]:
            continue
        cards.append(card)

    # "Aaj band hai" sinks a listing to the bottom for today and no longer —
    # tomorrow the same card ranks normally again. That's the difference
    # between a vendor's day off and a vendor who moved.
    cards.sort(key=lambda c: (
        1 if c["closed_today"] else 0,
        0 if c["is_open_now"] else 1,
        1 if c["trust"] == "doubtful" else 0,
        -len(c["matched"]),
        c["distance_km"],
    ))
    return {"query": q, "count": len(cards), "corrections": corrections,
            "vendors": cards[:limit]}


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
    listing is wrong, and how strongly depends entirely on *why*:

    - "aaj band hai"  → today's note only. Nothing held against the listing.
    - "yahan se hat gaya" → this spot looks wrong.
    - "hamesha ke liye band" → weighted heavily; two of these retire the card.

    A "haan hai" also clears today's closed flag: whoever is standing in front
    of the open shop is more current than whoever found it shut this morning.
    """
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Ye dukaan nahi mili")

    if payload.yes:
        shop.seen_yes = (shop.seen_yes or 0) + 1
        shop.last_seen_at = datetime.utcnow()
        shop.closed_today_at = None
    else:
        reason = food.normalise_seen_reason(payload.reason)
        if reason == "closed_today":
            shop.closed_today_at = datetime.utcnow()
        elif reason == "moved":
            shop.moved_count = (shop.moved_count or 0) + 1
        elif reason == "shut_down":
            shop.shutdown_count = (shop.shutdown_count or 0) + 1
        else:
            shop.seen_no = (shop.seen_no or 0) + 1

    db.commit()
    db.refresh(shop)
    return vendor_view(shop)


@router.post("/{shop_id}/report", response_model=schemas.ReportResponse)
def report_listing(shop_id: int, payload: schemas.ReportCreate, db: Session = Depends(get_db)):
    """Flag a listing as wrong — fake, joke, duplicate, offensive.

    Separate from the seen votes on purpose: a vote is about today, a report is
    about whether the listing should exist at all. Enough distinct people
    (food.REPORTS_TO_HIDE) pulls it out of search, reversibly — nothing is
    deleted, and the owner panel reviews and restores.

    One report per device: without this, a single annoyed person could bury a
    competitor by tapping the same button five times.
    """
    shop = db.get(models.Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Ye dukaan nahi mili")

    device_id = (payload.device_id or "").strip()
    if device_id:
        already = (
            db.query(models.ShopReport)
            .filter(models.ShopReport.shop_id == shop_id,
                    models.ShopReport.device_id == device_id)
            .first()
        )
        if already:
            return {
                "reported": False,
                "report_count": shop.report_count or 0,
                "hidden": bool(shop.hidden),
                "message": "Aap pehle hi report kar chuke ho.",
            }

    db.add(models.ShopReport(
        shop_id=shop_id,
        device_id=device_id,
        reason=food.normalise_report_reason(payload.reason),
        note=(payload.note or "").strip()[:500],
    ))
    shop.report_count = (shop.report_count or 0) + 1
    if shop.report_count >= food.REPORTS_TO_HIDE:
        shop.hidden = 1
    db.commit()
    db.refresh(shop)

    return {
        "reported": True,
        "report_count": shop.report_count,
        "hidden": bool(shop.hidden),
        "message": (
            "Report mil gayi — ye listing ab chhup gayi hai, review hogi."
            if shop.hidden else "Report mil gayi, shukriya."
        ),
    }


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
