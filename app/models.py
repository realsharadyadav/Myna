from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class AppSetting(Base):
    """Non-secret runtime settings stored in DB."""
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Shop(Base):
    __tablename__ = "shops"

    shop_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    shopkeeper = Column(String, default="")
    lat = Column(Float, nullable=False)
    long = Column(Float, nullable=False)
    address = Column(String, default="")
    phone = Column(String, default="")
    photo_url = Column(String, default="")
    # "fixed" = a shop at one address; "mobile" = thela/cart that moves between
    # stops (see ShopStop). Mobile shops are found through their stops, not
    # through lat/long, which for them is just wherever they registered.
    shop_type = Column(String, default="fixed")
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="shop", cascade="all, delete-orphan")
    stops = relationship(
        "ShopStop",
        back_populates="shop",
        cascade="all, delete-orphan",
        order_by="ShopStop.stop_id",
    )


class ShopStop(Base):
    """One place a mobile vendor stands, plus when they're there.

    "Gali no. 4, Sector 12 — every Tuesday, 10:00–12:00" is one row. A vendor
    doing a daily round of four corners has four rows with day_of_week = -1.
    """
    __tablename__ = "shop_stops"

    stop_id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.shop_id"), nullable=False, index=True)
    label = Column(String, default="")           # "Gali no. 4, near the temple"
    lat = Column(Float, nullable=False)
    long = Column(Float, nullable=False)
    address = Column(String, default="")
    day_of_week = Column(Integer, default=-1)    # 0=Mon … 6=Sun, -1 = every day
    start_time = Column(String, default="")      # local "HH:MM"
    end_time = Column(String, default="")
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="stops")


class Item(Base):
    __tablename__ = "items"

    item_id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.shop_id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, default="")
    photo_url = Column(String, default="")
    # Semantic-search vector (local BAAI/bge-small-en-v1.5 by default, or
    # Gemini text-embedding-004 if selected), JSON list of floats.
    # Empty string = not embedded yet (not backfilled).
    embedding = Column(String, default="")
    embedding_model = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="items")
