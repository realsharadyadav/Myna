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


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    shopkeeper: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class ShopOut(BaseModel):
    shop_id: int
    name: str
    shopkeeper: str
    lat: float
    long: float
    address: str
    phone: str
    photo_url: str
    created_at: datetime

    class Config:
        from_attributes = True


class ItemCreate(BaseModel):
    name: str
    category: Optional[str] = ""


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
