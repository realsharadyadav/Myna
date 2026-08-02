"""Does the configured model actually read photos?

Myna's onboarding leans on OCR: a shopkeeper photographs their name board and
the model reads the shop name off it. But the model picker happily accepts
text-only models (a Groq `gpt-oss-*`, say), and when one is selected every
photo silently produces nothing — the app just looks broken.

This module renders a small shop-board image with a known code on it, sends it
to a model, and reports back what happened, so the owner panel can say
"this model reads photos" or "this model can't take images at all" instead of
leaving it to be discovered in the field.
"""

import io
import random
import re
import string
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageDraw, ImageFont

from . import ai

_PROMPT = (
    "This is a photo of a shop's name board. Read the text on it. "
    "Reply with ONLY the text you can see, nothing else."
)

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _centred(draw, y, text, font, fill, width):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (right - left)) / 2 - left, y - top), text, font=font, fill=fill)
    return bottom - top


def make_test_image(code: str) -> bytes:
    """A mock shop board carrying `code` — the same kind of picture a
    shopkeeper would take during onboarding, so the test exercises the real
    task rather than an abstract one."""
    width, height = 640, 360
    img = Image.new("RGB", (width, height), "#F2C230")
    draw = ImageDraw.Draw(img)
    draw.rectangle([24, 24, width - 24, height - 24], fill="#FFFFFF", outline="#1B1A17", width=6)
    _centred(draw, 78, "MYNA TEST STORE", _font(52), "#1B1A17", width)
    _centred(draw, 158, code, _font(72), "#B4232A", width)
    _centred(draw, 258, "General Store", _font(34), "#5B5445", width)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _new_code() -> str:
    """A fresh code each run, so a passing result can't come from a cached
    response or from the model guessing a code it saw in a previous test."""
    letters = "".join(random.choice(string.ascii_uppercase) for _ in range(2))
    digits = "".join(random.choice(string.digits) for _ in range(4))
    return f"{letters}-{digits}"


def _explain(exc: Exception) -> tuple[str, bool]:
    """(message, looks_like_no_image_support) for a failed provider call."""
    detail = str(exc)
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            body = response.json()
            detail = (
                body.get("error", {}).get("message")
                or body.get("message")
                or response.text
            )
        except ValueError:
            detail = response.text
        detail = f"HTTP {response.status_code}: {detail}"
    lowered = detail.lower()
    no_images = any(
        hint in lowered
        for hint in (
            "image", "vision", "multimodal", "modality", "image_url",
            "does not support", "not supported", "unsupported",
        )
    )
    return detail.strip()[:400], no_images


def run(model_str: str = "", db_default: str = "") -> dict:
    """Send a generated shop board to `model_str` and report what came back.

    Returns a dict the owner panel renders directly:
      status  — 'pass'      the model read the code off the image
                'partial'   the model accepted the image but misread it
                'no_vision' the provider rejected the image (text-only model)
                'error'     network/auth/other failure
                'unconfigured' no provider key for this model
      expected/reply/detail/latency_ms/model for the details line.
    """
    resolved = ai.resolve_model(model_str) or ai.resolve_model(
        ai.get_effective_default(db_default) or ""
    )
    if not resolved:
        return {
            "status": "unconfigured",
            "model": model_str,
            "detail": "No API key configured for this provider — set one in .env.",
        }

    provider_name, model_id = resolved
    provider = ai.PROVIDERS[provider_name]
    code = _new_code()
    label = f"{provider_name}/{model_id}"

    tmp = NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(make_test_image(code))
        tmp.close()
        started = time.perf_counter()
        try:
            reply = provider["call"](provider["api_key"], model_id, tmp.name, _PROMPT) or ""
        except Exception as exc:  # provider errors carry the useful diagnosis
            detail, no_images = _explain(exc)
            return {
                "status": "no_vision" if no_images else "error",
                "model": label,
                "expected": code,
                "detail": detail,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        latency_ms = int((time.perf_counter() - started) * 1000)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    # Compare loosely: models format the reply differently ("MY-1234",
    # "my 1234", quoted, with the shop name attached), and none of that means
    # the OCR failed.
    def _squash(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    read_code = _squash(code) in _squash(reply)
    read_name = "mynateststore" in _squash(reply)

    if read_code:
        status, detail = "pass", "Read the board correctly — OCR works."
    elif read_name:
        status, detail = "partial", "Read the image but misread the code — OCR is weak on small text."
    elif reply:
        status, detail = "partial", "Replied, but nothing on the board was read back — likely not seeing the image."
    else:
        status, detail = "error", "Empty reply from the model."

    return {
        "status": status,
        "model": label,
        "expected": code,
        "reply": reply[:300],
        "detail": detail,
        "latency_ms": latency_ms,
    }
