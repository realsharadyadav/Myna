from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class Shop(Base):
    __tablename__ = "shops"

    shop_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    long = Column(Float, nullable=False)
    address = Column(String, default="")
    phone = Column(String, default="")
    photo_url = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="shop", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    item_id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.shop_id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, default="")
    photo_url = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="items")
