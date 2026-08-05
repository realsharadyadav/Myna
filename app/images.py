"""Shrinking photos, in one place.

A phone camera hands us 3-5 MB. Nothing downstream wants that:

  * the vision model gains nothing above ~1568px on the long edge, and
    Anthropic rejects a base64 image over 5 MB outright;
  * the card photo is displayed a few hundred pixels wide in a list, so
    storing the original means paying to serve pixels nobody sees — on the
    viewer's mobile data, not ours;
  * the upload itself is the slowest part of adding a jagah on 4G.

The last one is the browser's job (app/static/index.html shrinks before it
uploads). This module is the server-side guarantee: a client that skips it,
an old browser, or anything posting straight at the API still can't put a
5 MB original into storage.

EXIF orientation is honoured and then stripped. A portrait phone photo carries
its rotation as a flag rather than in the pixels, so re-encoding without
applying it first delivers a sideways board — which reads badly to a model and
looks broken on a card. Stripping the rest also drops the GPS coordinates
phones embed, which is not ours to publish.
"""
import io

# What the vision models can actually use. Above this the extra pixels cost
# tokens and latency and change nothing about what the model reads.
AI_MAX_EDGE = 1568
AI_QUALITY = 82

# What gets stored and served. The card shows it a few hundred pixels wide;
# this leaves room for a retina phone and a future detail view without
# carrying the original around forever.
STORED_MAX_EDGE = 1280
STORED_QUALITY = 78


def downscale(raw: bytes, max_edge: int, quality: int) -> bytes | None:
    """Re-encode down to max_edge as JPEG. None if the bytes can't be read.

    None means "leave the original alone" rather than "fail": losing a photo
    to a picky decoder is worse than storing one that's bigger than we'd like.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return None


def for_ai(raw: bytes) -> bytes | None:
    return downscale(raw, AI_MAX_EDGE, AI_QUALITY)


def for_storage(raw: bytes) -> bytes | None:
    return downscale(raw, STORED_MAX_EDGE, STORED_QUALITY)
