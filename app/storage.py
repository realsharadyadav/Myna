"""Where uploaded photos go.

Two jobs, deliberately kept apart:

    save_temp   bytes on local disk so the vision model can read them
    publish     the one photo kept for the card, put somewhere permanent

The split matters because Render's free filesystem is ephemeral — anything
written to local disk is gone on the next deploy. A temp file doesn't care;
it's deleted a few seconds later anyway. A published photo does: it's the
picture on the card, and it has to still be there next month.

So publish() sends it to Cloudinary when that's configured, and falls back to
local disk when it isn't. The fallback is for local dev. In production without
keys it will silently start losing photos again, so backend_name() reports
which path is live and the owner panel shows it next to the retention toggle.
"""
import hashlib
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile

from .config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    UPLOAD_DIR,
)

_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

CLOUDINARY_FOLDER = "myna"
_UPLOAD_TIMEOUT = 30.0


def remote_configured() -> bool:
    """True when published photos go somewhere that survives a deploy."""
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def backend_name() -> str:
    return "cloudinary" if remote_configured() else "local-disk"


def _suffix(filename: str | None) -> str:
    suffix = Path(filename or "photo.jpg").suffix.lower()
    return suffix if suffix in _ALLOWED else ".jpg"


def save_temp(file: UploadFile) -> str:
    """Write an upload to a private temp file and return its path.

    Never inside UPLOAD_DIR: these are read by the vision model and thrown
    away, and they must not be reachable over HTTP even for the seconds they
    exist.
    """
    tmp_dir = Path(tempfile.gettempdir()) / "myna-uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"{uuid.uuid4().hex}{_suffix(file.filename)}"
    dest.write_bytes(file.file.read())
    return str(dest)


def discard(path: str) -> None:
    """Delete a temp file, never raising — cleanup must not fail a request."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def publish(path: str) -> str:
    """Copy a temp photo to permanent storage and return its public URL.

    Returns "" if it couldn't be stored anywhere — the caller then saves a
    listing with no photo, which is a much better outcome than a card pointing
    at a URL that 404s.
    """
    source = Path(path)
    if not source.exists():
        return ""
    if remote_configured():
        url = _upload_to_cloudinary(source)
        if url:
            return url
        # Falling through to local disk would produce a URL that works today
        # and 404s after the next deploy. No photo is the honest answer.
        return ""
    return _copy_to_upload_dir(source)


def _copy_to_upload_dir(source: Path) -> str:
    """Dev fallback: keep it on local disk, served by the /uploads mount."""
    try:
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{source.suffix}"
        dest.write_bytes(source.read_bytes())
        return f"/uploads/{dest.name}"
    except OSError:
        return ""


def _signature(params: dict[str, str]) -> str:
    """Cloudinary's signed-upload scheme: sha1 of the sorted params + secret."""
    payload = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((payload + CLOUDINARY_API_SECRET).encode()).hexdigest()


def _upload_to_cloudinary(source: Path) -> str:
    signed = {"folder": CLOUDINARY_FOLDER, "timestamp": str(int(time.time()))}
    data = {
        **signed,
        "api_key": CLOUDINARY_API_KEY,
        "signature": _signature(signed),
    }
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    try:
        with source.open("rb") as handle:
            response = httpx.post(
                url,
                data=data,
                files={"file": (source.name, handle)},
                timeout=_UPLOAD_TIMEOUT,
            )
        response.raise_for_status()
        return response.json().get("secure_url", "")
    except (httpx.HTTPError, ValueError, KeyError):
        # A photo is worth less than the listing it belongs to. Losing the
        # picture is survivable; failing the whole add is not.
        return ""
