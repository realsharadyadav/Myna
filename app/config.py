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
DATABASE_URL = os.getenv("MYNA_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR}/myna.db"
# Render/Heroku hand out "postgres://" — SQLAlchemy needs "postgresql+psycopg://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Photo storage (app/storage.py). Render's free filesystem is ephemeral, so
# UPLOAD_DIR above only survives until the next deploy — fine for the temp
# files the vision model reads, useless for the photo shown on a card. Set
# these three and published photos go to Cloudinary instead; leave them unset
# and it falls back to local disk, which is a dev convenience only.
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

# AI vision providers. Set whichever keys you have; the first configured
# provider becomes the default unless overridden in the DB (admin panel).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Web search grounding (app/web_search.py) — kept for trending and
# weather-based suggestions, which aren't built yet. Exa when configured,
# free/keyless DuckDuckGo otherwise.
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# Local timezone for mobile-vendor rounds (app/schedule.py). Cart timings are
# typed and read locally ("har mangal 10 se 12"), so they're stored as local
# clock times and compared against this zone.
TIMEZONE = os.getenv("MYNA_TIMEZONE", "Asia/Kolkata")

# Reverse geocoding (OpenStreetMap Nominatim - free, rate-limited)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "myna-hyperlocal-finder/1.0"

# CORS: the frontend (app/static, published as its own Render static site —
# see render.yaml) now calls this API cross-origin. "*" (default) keeps
# everything open — there's no auth/cookies here, so a permissive policy
# carries no extra risk. Tighten via MYNA_ALLOWED_ORIGINS once the static
# site's onrender.com URL is known.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("MYNA_ALLOWED_ORIGINS", "*").split(",") if o.strip()] or ["*"]
