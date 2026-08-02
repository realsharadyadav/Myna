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

_SETTING_DEFAULT_MODEL = "default_model"


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


def get_default_model(db) -> str:
    """Return the currently selected default LLM model ('provider/model') or ''."""
    return get_setting(db, _SETTING_DEFAULT_MODEL, "")


def set_default_model(db, model: str) -> None:
    set_setting(db, _SETTING_DEFAULT_MODEL, model)
