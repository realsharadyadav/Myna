import tempfile
import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import UPLOAD_DIR

_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def save_upload(file: UploadFile, retain: bool = False) -> tuple[str, str]:
    """Save an uploaded image.

    Returns (local_path, public_url).
    When retain is False, the file is written to a temp location outside the
    publicly-mounted uploads directory (so it's never web-accessible) and
    public_url is empty — caller is responsible for deleting the temp file.
    When retain is True, the file is written to UPLOAD_DIR and public_url
    is set so it can be served permanently.
    """
    suffix = Path(file.filename or "photo.jpg").suffix.lower()
    if suffix not in _ALLOWED:
        suffix = ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"

    if retain:
        dest = UPLOAD_DIR / filename
        dest.write_bytes(file.file.read())
        return str(dest), f"/uploads/{filename}"

    tmp_dir = Path(tempfile.gettempdir()) / "myna-uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / filename
    dest.write_bytes(file.file.read())
    return str(dest), ""
