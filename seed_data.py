"""Seed Myna with sample data — 50 shops across Mumbai.

Usage:
  Local (SQLite):
      ./.venv/bin/python seed_data.py

  Render Postgres (one-shot, password stays out of the repo):
      SEED_DATABASE_URL="postgresql://user:pass@host:5432/db" ./.venv/bin/python seed_data.py

The DB is wiped of shops/items first, so it's safe to re-run.
"""
import os
from datetime import datetime, timedelta

# Override the DB before importing app.database/config (which reads env once).
_override = os.getenv("SEED_DATABASE_URL")
if _override:
    os.environ["MYNA_DATABASE_URL"] = _override

os.environ.setdefault("MYNA_SKIP_DOTENV", "1")

from app import models  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.config import DATABASE_URL  # noqa: E402
from app.sample_data import build_shops  # noqa: E402


def seed(total: int = 50):
    shops = build_shops(total)
    print(f"Seeding into: {DATABASE_URL}")
    db = SessionLocal()
    try:
        # Wipe existing data (keeps shops/items consistent on re-runs).
        db.query(models.Item).delete()
        db.query(models.Shop).delete()

        count_items = 0
        now = datetime.utcnow()
        for i, shop_data in enumerate(shops):
            shop = models.Shop(
                name=shop_data["name"],
                shopkeeper=shop_data["shopkeeper"],
                lat=shop_data["lat"],
                long=shop_data["long"],
                address=shop_data["address"],
                phone=shop_data["phone"],
                created_at=now - timedelta(days=len(shops) - i),
            )
            db.add(shop)
            db.flush()  # assign shop_id
            for name, category in shop_data["items"]:
                db.add(models.Item(
                    shop_id=shop.shop_id,
                    name=name,
                    category=category,
                    created_at=now - timedelta(days=len(shops) - i),
                ))
                count_items += 1

        db.commit()
        print(f"Seeded {len(shops)} shops and {count_items} items.")
        for s in shops[:8]:
            print(f"  - {s['name']} ({len(s['items'])} items)")
        print(f"  … and {len(shops) - 8} more.")
    finally:
        db.close()


if __name__ == "__main__":
    # Ensure tables exist (first run on a fresh Postgres).
    models.Base.metadata.create_all(bind=engine)
    seed()
