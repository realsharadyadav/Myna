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


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None


class ItemOut(BaseModel):
    item_id: int
    shop_id: int
    name: str
    category: str
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
