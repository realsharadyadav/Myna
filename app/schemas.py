from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    # Spellings that were corrected, {typed: used}. Surfaced rather than applied
    # silently: a search that quietly looks for a different word than the one
    # you typed is how people stop trusting results they can't explain.
    corrections: dict[str, str] = {}
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
    created_at: datetime


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
    created_at: datetime
