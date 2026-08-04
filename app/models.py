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
    # What kind of food vendor this is — see app/food.py (thela, chaat, chai,
    # dhaba …). Drives the card's icon and the "kya chahiye" filters.
    food_kind = Column(String, default="other")
    # Anyone can add any thela, so a listing carries who put it there (an
    # anonymous device id, not an account) and how the street has voted on it
    # since. `seen_yes`/`seen_no` are the freshness signal that replaces asking
    # a vendor to keep their own listing updated — they never will.
    added_by = Column(String, default="")
    seen_yes = Column(Integer, default=0)
    # "Nahi mila" split by what it actually means — see food.SEEN_REASONS.
    # Lumping these together is what kills a good listing over one holiday:
    # `closed_today_at` is a note about today, `moved_count` argues the spot is
    # wrong, and `shutdown_count` argues the vendor is gone for good.
    seen_no = Column(Integer, default=0)          # reason not given
    moved_count = Column(Integer, default=0)
    shutdown_count = Column(Integer, default=0)
    closed_today_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    # Reports are about the listing existing at all, not about today. Enough of
    # them from distinct people hides it from search — reversibly, never
    # deleted, for the owner panel to review.
    report_count = Column(Integer, default=0)
    hidden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship(
        "ShopReport", back_populates="shop", cascade="all, delete-orphan"
    )

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


class ShopReport(Base):
    """One person flagging a listing as wrong — fake, joke, duplicate.

    Stored per row rather than as a bare counter so the same device can't flag
    the same listing repeatedly, and so the owner panel can see *why* something
    was reported instead of only how often.
    """
    __tablename__ = "shop_reports"

    report_id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.shop_id"), nullable=False, index=True)
    device_id = Column(String, default="", index=True)
    reason = Column(String, default="wrong")
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="reports")


class Item(Base):
    __tablename__ = "items"

    item_id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.shop_id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, default="")
    # Rupees. 0 = the board didn't show a price (never guessed by the AI), so
    # the card shows nothing rather than a made-up number.
    price = Column(Float, default=0.0)
    photo_url = Column(String, default="")
    # Semantic-search vector (local BAAI/bge-small-en-v1.5 by default, or
    # Gemini text-embedding-004 if selected), JSON list of floats.
    # Empty string = not embedded yet (not backfilled).
    embedding = Column(String, default="")
    embedding_model = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="items")
