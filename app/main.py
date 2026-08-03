from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import ALLOWED_ORIGINS, BASE_DIR
from .database import (
    Base,
    SessionLocal,
    engine,
    get_default_search_model,
    get_default_vision_model,
    set_default_search_model,
    set_default_vision_model,
)
from . import ai
from .routers import admin, food, items, search, shops

Base.metadata.create_all(bind=engine)

# Lightweight migrations for DBs created before a column existed
# (SQLite + Postgres compatible).
def _columns(conn, table: str) -> list[str]:
    if engine.url.get_backend_name() == "sqlite":
        return [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))]
    return [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name=:t"
    ), {"t": table})]


with engine.connect() as conn:
    # items.embedding* — added when semantic search landed.
    cols = _columns(conn, "items")
    if "embedding" not in cols:
        conn.execute(text("ALTER TABLE items ADD COLUMN embedding VARCHAR DEFAULT ''"))
        conn.commit()
    if "embedding_model" not in cols:
        conn.execute(text("ALTER TABLE items ADD COLUMN embedding_model VARCHAR DEFAULT ''"))
        conn.commit()
    if "price" not in cols:
        conn.execute(text("ALTER TABLE items ADD COLUMN price FLOAT DEFAULT 0"))
        conn.execute(text("UPDATE items SET price=0 WHERE price IS NULL"))
        conn.commit()
    # shops.shop_type — added for mobile vendors (thela/cart) with stops.
    shop_cols = _columns(conn, "shops")
    if "shop_type" not in shop_cols:
        conn.execute(text("ALTER TABLE shops ADD COLUMN shop_type VARCHAR DEFAULT 'fixed'"))
        conn.execute(text("UPDATE shops SET shop_type='fixed' WHERE shop_type IS NULL"))
        conn.commit()
    # Food pivot + crowdsourced listings: vendor kind, who added it, and the
    # "abhi bhi yahan hai?" vote counts.
    for column, ddl, backfill in (
        ("food_kind", "ALTER TABLE shops ADD COLUMN food_kind VARCHAR DEFAULT 'other'",
         "UPDATE shops SET food_kind='other' WHERE food_kind IS NULL"),
        ("added_by", "ALTER TABLE shops ADD COLUMN added_by VARCHAR DEFAULT ''",
         "UPDATE shops SET added_by='' WHERE added_by IS NULL"),
        ("seen_yes", "ALTER TABLE shops ADD COLUMN seen_yes INTEGER DEFAULT 0",
         "UPDATE shops SET seen_yes=0 WHERE seen_yes IS NULL"),
        ("seen_no", "ALTER TABLE shops ADD COLUMN seen_no INTEGER DEFAULT 0",
         "UPDATE shops SET seen_no=0 WHERE seen_no IS NULL"),
        ("last_seen_at", "ALTER TABLE shops ADD COLUMN last_seen_at TIMESTAMP", ""),
    ):
        if column not in shop_cols:
            conn.execute(text(ddl))
            if backfill:
                conn.execute(text(backfill))
            conn.commit()

def _seed_default_models() -> None:
    """Persist per-feature default models if unset, so a fresh DB (or one
    wiped by re-seeding) works out of the box instead of silently falling
    back. Only fills empty settings — owner choices in the admin panel win.

    Embedding models aren't seeded here: they're a separate model family from
    vision/text chat models (embeddings.DEFAULT_MODEL already covers the
    zero-config case), so seeding it with a chat-model default would be
    meaningless."""
    effective = ai.get_effective_default("")
    if not effective:
        return
    db = SessionLocal()
    try:
        if not get_default_vision_model(db):
            set_default_vision_model(db, effective)
        if not get_default_search_model(db):
            set_default_search_model(db, effective)
    finally:
        db.close()


_seed_default_models()

app = FastAPI(title="Myna — Hyperlocal Shop & Product Finder")

# The frontend can now be deployed as its own static site (render.yaml) that
# calls this API cross-origin, so CORS has to be open for it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(food.router)
app.include_router(shops.router)
app.include_router(items.router)
app.include_router(items.catalog_router)
app.include_router(search.router)
app.include_router(admin.router)

app.mount("/uploads", StaticFiles(directory=BASE_DIR / "uploads"), name="uploads")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    """The food app — two screens, no login. See app/static/khana.html."""
    return FileResponse(BASE_DIR / "app" / "static" / "khana.html")


@app.get("/classic", include_in_schema=False)
def classic():
    """The original general-purpose product search, kept for the admin panel's
    demo data and for anyone still pointed at it."""
    return FileResponse(BASE_DIR / "app" / "static" / "index.html")


@app.get("/shopkeeper", include_in_schema=False)
def shopkeeper():
    return FileResponse(BASE_DIR / "app" / "static" / "shopkeeper.html")


@app.get("/admin", include_in_schema=False)
def admin():
    return FileResponse(BASE_DIR / "app" / "static" / "admin.html")


# Catch-all for root-relative assets (myna-logo.svg, config.js) referenced by
# the pages above. Registered last so the explicit routes above still win —
# this only serves whatever those routes don't handle. Also matches what the
# split-off static frontend does, since it publishes this same directory as
# its site root.
app.mount("/", StaticFiles(directory=BASE_DIR / "app" / "static"), name="assets")
