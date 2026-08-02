from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ShopCreate(BaseModel):
    name: str
    lat: float
    long: float
    address: Optional[str] = ""
    phone: Optional[str] = ""


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class ShopOut(BaseModel):
    shop_id: int
    name: str
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


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None


class ItemOut(BaseModel):
    item_id: int
    shop_id: int
    name: str
    category: str
    photo_url: str
    created_at: datetime

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    shop_id: int
    shop_name: str
    address: str
    phone: str
    distance_km: float
    item_id: int
    item_name: str
    item_category: str
    item_photo_url: str


class AISuggestion(BaseModel):
    suggestion: str
