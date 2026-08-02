import os
from pathlib import Path

from dotenv import load_dotenv

if not os.getenv("MYNA_SKIP_DOTENV"):
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database selection priority:
#   1. MYNA_DATABASE_URL — explicit override (e.g. set in .env or Render env vars)
#   2. DATABASE_URL      — auto-injected by Render/Heroku when a database is linked
#   3. SQLite file       — zero-config local dev fallback
DATABASE_URL = os.getenv(
    "MYNA_DATABASE_URL",
    os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/myna.db"),
)
# Render/Heroku hand out "postgres://" — SQLAlchemy needs "postgresql+psycopg://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# AI vision providers. Set whichever keys you have; the first configured
# provider becomes the default unless overridden in the DB (admin panel).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Reverse geocoding (OpenStreetMap Nominatim - free, rate-limited)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "myna-hyperlocal-finder/1.0"
