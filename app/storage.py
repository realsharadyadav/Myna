import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import UPLOAD_DIR

_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def save_upload(file: UploadFile) -> str:
    """Save an uploaded image and return its public URL path (/uploads/...)."""
    suffix = Path(file.filename or "photo.jpg").suffix.lower()
    if suffix not in _ALLOWED:
        suffix = ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(file.file.read())
    return f"/uploads/{filename}"
