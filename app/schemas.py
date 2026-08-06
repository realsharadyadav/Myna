from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel


def _as_utc(dt: datetime) -> datetime:
    """Every `created_at` in this app comes from `datetime.utcnow()` — naive,
    but always UTC. Serialized as-is, a browser's `new Date(...)` reads the
    missing offset as *local* time instead, so admin.html showed a shop as
    created hours off from when it actually was. Tagging it here makes the
    JSON carry the offset, so the browser converts it correctly instead of
    guessing."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


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
    created_at: UtcDatetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Mobile vendors: stops (place + weekly/daily time window)
# ---------------------------------------------------------------------------

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
    # "product" | "service". Left blank it's inferred from the name, so
    # "watch repair" lands as a service without the client having to say so.
    kind: Optional[str] = ""


# ---------------------------------------------------------------------------
# Survey add: mapping a village on foot
# ---------------------------------------------------------------------------
# The photo add flow reads a board, which only works where there is one. A
# hardware shop has no board listing its stock, and no shop anywhere has a
# board listing what it can repair — so the things hardest to find are exactly
# the things no camera can capture. They get typed, on the spot, by whoever
# walked in and asked.

class SurveyItem(BaseModel):
    name: str
    category: Optional[str] = ""
    price: Optional[float] = 0.0
    # Blank means "work it out from the name".
    kind: Optional[str] = ""


class SurveyAdd(BaseModel):
    # Set to add to a shop already mapped rather than creating a second copy
    # of it — the surveyor walking back past a shop they did an hour ago.
    shop_id: Optional[int] = None
    name: str
    kind: Optional[str] = ""
    shopkeeper: Optional[str] = ""
    lat: float
    long: float
    address: Optional[str] = ""
    phone: Optional[str] = ""
    device_id: Optional[str] = ""
    items: list[SurveyItem] = []


class SurveyResponse(BaseModel):
    created: bool           # False when an existing shop was added to
    vendor: "FoodVendorOut"
    items_added: int
    items_skipped: int      # already listed here (same name + kind)


# ---------------------------------------------------------------------------
# Food app: one-photo add, "paas me kya hai" browse, freshness votes
# ---------------------------------------------------------------------------

class MenuItemOut(BaseModel):
    item_id: int
    name: str
    category: str
    price: float = 0.0
    kind: str = "product"


class FoodVendorOut(BaseModel):
    """One card on the home screen — everything it needs, nothing more."""
    shop_id: int
    name: str
    food_kind: str
    kind_label: str
    kind_emoji: str
    # 'food' | 'goods' | 'services', and whether presence expires — the card
    # hides the "abhi hai?" prompt for a shop that doesn't need confirming.
    family: str = "food"
    family_label: str = ""
    perishable: bool = True
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
    # Spellings that were corrected, {typed: used}. Surfaced rather than applied
    # silently: a search that quietly looks for a different word than the one
    # you typed is how people stop trusting results they can't explain.
    corrections: dict[str, str] = {}
    vendors: list[FoodVendorOut]


class PlanItemOut(BaseModel):
    """One line of an AI-generated shopping list, plus the nearest shop that
    has it, if any nearby listing matched."""
    name: str
    note: str = ""
    shop: Optional[FoodVendorOut] = None


class PlanResponse(BaseModel):
    """"biryani" / "birthday party" / "leaking tap" -> the shopping list for
    it. `error` is set only when nothing could be generated at all — a
    generated item with no matching shop nearby is still a normal item."""
    query: str = ""
    items: list[PlanItemOut] = []
    error: str = ""


class QuickAddResponse(BaseModel):
    """What the one-photo add flow returns: the vendor it just created."""
    created: bool
    vendor: Optional[FoodVendorOut] = None
    # What the AI read, so the confirm screen can show "yeh sahi hai?" without
    # a second round-trip.
    read_name: str = ""
    read_kind: str = ""
    item_count: int = 0
    photo_count: int = 0
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
    created_at: UtcDatetime


class AdminVendor(BaseModel):
    """One row in the owner panel's vendor list."""
    shop_id: int
    name: str
    food_kind: str
    kind_label: str
    kind_emoji: str
    address: str
    menu_count: int
    round_count: int
    seen_yes: int
    report_count: int
    hidden: bool
    created_at: UtcDatetime


class AdminPhoto(BaseModel):
    """One kept photo, for the owner panel's moderation grid."""
    shop_id: int
    name: str
    photo_url: str
    added_by: str
    hidden: bool
    created_at: UtcDatetime
