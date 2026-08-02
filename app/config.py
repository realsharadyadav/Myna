import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/myna.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# AI vision providers. Set whichever keys you have; the first configured
# provider becomes the default unless MYNA_DEFAULT_MODEL overrides it.
# Format for MYNA_DEFAULT_MODEL: "provider/model"  e.g. "anthropic/claude-sonnet-4-20250514"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MYNA_DEFAULT_MODEL = os.getenv("MYNA_DEFAULT_MODEL", "")

# Reverse geocoding (OpenStreetMap Nominatim - free, rate-limited)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "myna-hyperlocal-finder/1.0"
