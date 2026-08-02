from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Non-secret runtime settings (stored in DB so they survive restarts)
# ---------------------------------------------------------------------------

_SETTING_RETAIN_IMAGES = "retain_uploaded_images"
_SETTING_VISION_MODEL = "default_vision_model"
_SETTING_SEARCH_MODEL = "default_search_model"
_SETTING_EMBEDDING_MODEL = "default_embedding_model"


def get_setting(db, key: str, default: str = "") -> str:
    """Read a setting from the app_settings table."""
    from . import models
    row = db.get(models.AppSetting, key)
    return row.value if row else default


def set_setting(db, key: str, value: str) -> None:
    """Write a setting to the app_settings table."""
    from . import models
    row = db.get(models.AppSetting, key)
    if row:
        row.value = value
    else:
        row = models.AppSetting(key=key, value=value)
        db.add(row)
    db.commit()


def get_retain_uploaded_images(db) -> bool:
    """Return whether uploaded images should be permanently stored."""
    val = get_setting(db, _SETTING_RETAIN_IMAGES, "false").lower()
    return val == "true"


def set_retain_uploaded_images(db, retain: bool) -> None:
    set_setting(db, _SETTING_RETAIN_IMAGES, "true" if retain else "false")


def get_default_vision_model(db) -> str:
    return get_setting(db, _SETTING_VISION_MODEL, "")


def set_default_vision_model(db, model: str) -> None:
    set_setting(db, _SETTING_VISION_MODEL, model)


def get_default_search_model(db) -> str:
    return get_setting(db, _SETTING_SEARCH_MODEL, "")


def set_default_search_model(db, model: str) -> None:
    set_setting(db, _SETTING_SEARCH_MODEL, model)


def get_default_embedding_model(db) -> str:
    return get_setting(db, _SETTING_EMBEDDING_MODEL, "")


def set_default_embedding_model(db, model: str) -> None:
    set_setting(db, _SETTING_EMBEDDING_MODEL, model)
