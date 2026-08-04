from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ShopCreate(BaseModel):
    name: str
    shopkeeper: Optional[str] = ""
    lat: float
    long: float
    address: Optional[str] = ""
    phone: Optional[str] = ""
    # "fixed" (default) or "mobile" for a thela/cart that moves between stops.
    shop_type: Optional[str] = "fixed"


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    shopkeeper: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    shop_type: Optional[str] = None


class ShopOut(BaseModel):
    shop_id: int
    name: str
    shopkeeper: str
    lat: float
    long: float
    address: str
    phone: str
    photo_url: str
    shop_type: str = "fixed"
    food_kind: str = "other"
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Mobile vendors: stops (place + weekly/daily time window)
# ---------------------------------------------------------------------------

class StopCreate(BaseModel):
    label: Optional[str] = ""
    lat: float
    long: float
    address: Optional[str] = ""
    day_of_week: int = -1          # 0=Mon … 6=Sun, -1 = every day
    start_time: Optional[str] = ""  # local "HH:MM"
    end_time: Optional[str] = ""
    note: Optional[str] = ""


class StopUpdate(BaseModel):
    label: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    address: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None


class StopOut(BaseModel):
    """Stored stop fields plus what app/schedule.py derives from them."""
    stop_id: int
    shop_id: int
    label: str
    lat: float
    long: float
    address: str
    day_of_week: int
    start_time: str
    end_time: str
    note: str
    # Distance from the searching customer to this stop. Only meaningful in
    # search responses; None when the stop is listed outside a search.
    distance_km: Optional[float] = None
    when: str = ""          # "Every Tuesday · 10 AM – 12 PM"
    status: str = ""        # 'here_now' | 'today' | 'upcoming'
    status_text: str = ""   # "Here now · till 12 PM"
    rank: int = 0           # 0 here now, 1 later today, 2 another day


class ItemCreate(BaseModel):
    name: str
    category: Optional[str] = ""
    price: Optional[float] = 0.0


class BulkItemsCreate(BaseModel):
    """Payload for adding a whole checkbox-selection of items at once."""
    items: list[ItemCreate]


class BulkItemsResult(BaseModel):
    added: list["ItemOut"]
    skipped: list[str]      # names the shop already had, reported back so the
                            # UI can say "12 added, 3 already in your list"


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None


class ItemOut(BaseModel):
    item_id: int
    shop_id: int
    name: str
    category: str
    price: float = 0.0
    photo_url: str
    embedding_model: str
    created_at: datetime

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    shop_id: int
    shop_name: str
    shopkeeper: str
    address: str
    phone: str
    # Shop coordinates travel with the result so the app can offer a
    # "directions" link straight to the shop.
    shop_lat: float = 0.0
    shop_long: float = 0.0
    distance_km: float
    item_id: int
    item_name: str
    item_category: str
    item_photo_url: str
    matched_term: str = ""
    coverage_count: int = 1
    coverage_total: int = 1
    # For a mobile vendor, shop_lat/shop_long above are the matched *stop's*
    # coordinates (distance and directions have to point at where the cart
    # actually stands), and `stop` says which stop that is and when.
    shop_type: str = "fixed"
    stop: Optional[StopOut] = None


class ShopSearchResult(BaseModel):
    """Agentic pipeline output: one entry per shop with coverage scoring."""
    shop_id: int
    shop_name: str
    shopkeeper: str
    address: str
    phone: str
    shop_lat: float = 0.0
    shop_long: float = 0.0
    distance_km: float
    coverage_count: int
    coverage_total: int
    shop_type: str = "fixed"
    stop: Optional[StopOut] = None
    # Every other round this vendor does, so the card can offer "or catch him
    # in Gali 9 on Friday".
    stops: list[StopOut] = []
    items: list[SearchResult]


# Shopping list composed of one representative product per parsed item,
# picked from the nearest shop that stocks it.
class ShoppingListItem(BaseModel):
    item: str          # parsed shopping-list term, e.g. "milk" or "doodh"
    product: str       # matched product name, e.g. "Amul Gold Milk 1L"
    category: str
    photo_url: str
    shop_id: int
    shop_name: str
    distance_km: float
    in_stock: bool = True
    shop_type: str = "fixed"
    # For mobile vendors: "Here now · till 12 PM", "Tue 10 AM – 12 PM".
    availability: str = ""


class OneTapSearchResponse(BaseModel):
    """Single-shot response: parsed items, shop matches, and a shopping list."""
    query: str
    items: list[str]
    method: str  # 'llm' or 'fallback'
    shopping_list: list[ShoppingListItem]
    shops: list[ShopSearchResult]


class AgentSearchResponse(BaseModel):
    """Top-level response of the agentic search pipeline."""
    query: str
    items: list[str]
    method: str  # 'llm' or 'fallback'
    shops: list[ShopSearchResult]


class AISuggestion(BaseModel):
    suggestion: str
    # Why the read failed, in words a shopkeeper can act on. Empty on success.
    error: str = ""


# ---------------------------------------------------------------------------
# Food app: one-photo add, "paas me kya hai" browse, freshness votes
# ---------------------------------------------------------------------------

class MenuItemOut(BaseModel):
    item_id: int
    name: str
    category: str
    price: float = 0.0


class FoodVendorOut(BaseModel):
    """One card on the home screen — everything it needs, nothing more."""
    shop_id: int
    name: str
    food_kind: str
    kind_label: str
    kind_emoji: str
    address: str
    phone: str
    photo_url: str
    lat: float
    long: float
    distance_km: float
    # Where a moving thela is *right now* — the stop it's standing at, if any,
    # otherwise the next one it's due at.
    shop_type: str = "fixed"
    stop: Optional[StopOut] = None
    stops: list[StopOut] = []
    open_text: str = ""      # "Abhi yahan hai · 12 baje tak"
    is_open_now: bool = False
    menu: list[MenuItemOut] = []
    matched: list[str] = []  # which searched dishes this vendor has
    # Crowdsourced freshness, in words: "Aaj dekha gaya", "3 din pehle".
    seen_text: str = ""
    seen_yes: int = 0
    seen_no: int = 0
    # 'fresh' | 'ok' | 'stale' | 'new' | 'doubtful' | 'closed'
    trust: str = "new"
    # Someone said it's shut *today* — a note, not a mark against the listing.
    closed_today: bool = False
    moved_count: int = 0
    shutdown_count: int = 0
    report_count: int = 0
    hidden: bool = False


class NearResponse(BaseModel):
    query: str = ""
    count: int
    vendors: list[FoodVendorOut]


class QuickAddResponse(BaseModel):
    """What the one-photo add flow returns: the vendor it just created."""
    created: bool
    vendor: Optional[FoodVendorOut] = None
    # What the AI read, so the confirm screen can show "yeh sahi hai?" without
    # a second round-trip.
    read_name: str = ""
    read_kind: str = ""
    item_count: int = 0
    error: str = ""


class SeenReport(BaseModel):
    """A passer-by answering "abhi bhi yahan hai?".

    On a "no", `reason` is what separates a vendor's day off from a vendor who
    has gone for good — see food.SEEN_REASONS. Omitting it is allowed and
    treated as "pata nahi".
    """
    yes: bool
    reason: Optional[str] = ""
    device_id: Optional[str] = ""


class ReportCreate(BaseModel):
    """Flagging a listing as wrong — fake, joke, duplicate, offensive."""
    reason: Optional[str] = ""
    note: Optional[str] = ""
    device_id: Optional[str] = ""


class ReportResponse(BaseModel):
    reported: bool           # False when this device had already flagged it
    report_count: int
    hidden: bool
    message: str


class ReportedVendor(BaseModel):
    """A flagged listing as the owner panel needs to see it."""
    shop_id: int
    name: str
    kind_label: str
    address: str
    added_by: str
    report_count: int
    hidden: bool
    seen_yes: int
    shutdown_count: int
    reasons: dict[str, int]      # {"fake": 2, "duplicate": 1}
    notes: list[str]
    created_at: datetime
