"""Semantic search embeddings via Gemini text-embedding-004 (free tier).

Vectors are stored as a JSON string on items.embedding — at pilot scale
(~thousands of items) brute-force cosine similarity in Python takes single-digit
milliseconds, so no vector DB is needed. Swap for pgvector/sqlite-vec if the
catalogue grows past ~50k items.

An in-process cache avoids re-reading/parsing every item row on each search.
Invalidate via invalidate_cache() whenever items change.

Graceful degradation: everything is a no-op without GEMINI_API_KEY — search
then runs in substring-only mode.
"""

import json
import math

import httpx

from .config import GEMINI_API_KEY
from .database import get_default_embedding_model
from sqlalchemy.orm import Session

_MODEL = "text-embedding-004"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:embedContent"
_BATCH_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:batchEmbedContents"

# Flipped to False permanently after the first network/auth failure, so a bad
# GEMINI_API_KEY doesn't spam the API on every search.
_ok = True

# (item_id, shop_id, unit-normalized vector), populated by _ensure_cache().
_CACHE: list[tuple[int, int, tuple[float, ...]]] | None = None
_keys: list[tuple[int, int]] | None = None


def enabled() -> bool:
    return bool(GEMINI_API_KEY) and _ok


def _mark_failed() -> None:
    global _ok
    _ok = False


def _normalize(vec: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


def embed_text(text: str, model: str = "") -> list[float] | None:
    """Embed one string. Returns None without a key or on API failure."""
    if not GEMINI_API_KEY or not text.strip():
        return None
    effective_model = _MODEL
    if model:
        # Handle "provider:model_id" format - extract just the model id.
        if ":" in model:
            effective_model = model.split(":", 1)[1]
        elif "/" in model:
            effective_model = model.split("/", 1)[1]
        else:
            effective_model = model
    try:
        resp = httpx.post(
            _URL,
            params={"key": GEMINI_API_KEY},
            json={"model": f"models/{effective_model}",
                  "content": {"parts": [{"text": text.strip()[:2000]}]}},
            timeout=20.0,
        )
        resp.raise_for_status()
        values = resp.json().get("embedding", {}).get("values")
        return list(values) if values else None
    except Exception:
        _mark_failed()
        return None


def embed_texts(texts: list[str], model: str = "") -> list[list[float] | None]:
    """Batch embed (used for backfill). Falls back to per-text calls if the
    batch endpoint fails."""
    if not GEMINI_API_KEY or not texts:
        return [None] * len(texts)
    effective_model = _MODEL
    if model:
        if ":" in model:
            effective_model = model.split(":", 1)[1]
        elif "/" in model:
            effective_model = model.split("/", 1)[1]
        else:
            effective_model = model
    try:
        resp = httpx.post(
            _BATCH_URL,
            params={"key": GEMINI_API_KEY},
            json={"requests": [
                {"model": f"models/{effective_model}",
                 "content": {"parts": [{"text": t.strip()[:2000]}]}}
                for t in texts
            ]},
            timeout=60.0,
        )
        resp.raise_for_status()
        embs = resp.json().get("embeddings", [])
        out: list[list[float] | None] = []
        for i in range(len(texts)):
            values = embs[i].get("values") if i < len(embs) else None
            out.append(list(values) if values else None)
        return out
    except Exception:
        return [embed_text(t, model=model) for t in texts]


def item_text(item) -> str:
    """The text we embed for an item — name plus category for context."""
    return f"{item.name} — {item.category}" if item.category else item.name


def embed_item(item, db=None) -> None:
    """(Re)generate and store one item's embedding in place."""
    model = ""
    if db is not None:
        model = get_default_embedding_model(db)
    effective_model = model or _MODEL
    vec = embed_text(item_text(item), model=model)
    if vec:
        item.embedding = json.dumps(vec)
        item.embedding_model = effective_model


def backfill(db: Session, batch_size: int = 100) -> int:
    """Embed every item that doesn't have a vector yet, or whose
    embedding_model doesn't match the current default. Returns count embedded."""
    from . import models
    default_model = get_default_embedding_model(db) or _MODEL
    pending = (
        db.query(models.Item)
        .filter(
            (models.Item.embedding == "") | (models.Item.embedding.is_(None)) |
            (models.Item.embedding_model != default_model)
        )
        .all()
    )
    done = 0
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        vectors = embed_texts([item_text(it) for it in batch], model=default_model)
        for item, vec in zip(batch, vectors):
            if vec:
                item.embedding = json.dumps(vec)
                item.embedding_model = default_model
                done += 1
        db.commit()
    if done:
        invalidate_cache()
    return done


def invalidate_cache() -> None:
    global _CACHE, _keys
    _CACHE = None
    _keys = None


def _ensure_cache(db: Session) -> None:
    global _CACHE, _keys
    if _CACHE is not None:
        return
    from . import models
    default_model = get_default_embedding_model(db) or _MODEL
    cache: list[tuple[int, int, tuple[float, ...]]] = []
    keys: list[tuple[int, int]] = []
    rows = (
        db.query(models.Item)
        .filter(
            models.Item.embedding != "",
            models.Item.embedding.isnot(None),
            models.Item.embedding_model == default_model,
        )
        .all()
    )
    for item in rows:
        try:
            vec = json.loads(item.embedding)
        except (ValueError, TypeError):
            continue
        if not isinstance(vec, list) or not vec:
            continue
        cache.append((item.item_id, item.shop_id, _normalize(vec)))
        keys.append((item.item_id, item.shop_id))
    _CACHE = cache
    _keys = keys


def fetch_embedding_models() -> list[dict]:
    """List embedding-capable models. Only Gemini is implemented as an
    embedding backend, so this queries Gemini's model list directly rather
    than ai.fetch_all_models() (which excludes embedding models entirely,
    since it's meant for vision/text chat models)."""
    if not GEMINI_API_KEY:
        return []
    try:
        resp = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": GEMINI_API_KEY},
            timeout=30.0,
        )
        resp.raise_for_status()
        out = []
        for m in resp.json().get("models", []):
            if "embedContent" not in m.get("supportedGenerationMethods", []):
                continue
            mid = m.get("name", "").replace("models/", "")
            out.append({
                "provider": "gemini",
                "model": mid,
                "label": f"gemini/{mid}",
                "display_name": m.get("displayName", mid),
            })
        return out
    except Exception:
        return [{
            "provider": "gemini",
            "model": _MODEL,
            "label": f"gemini/{_MODEL}",
            "display_name": _MODEL,
        }]


def similar_items(db: Session, term: str, threshold: float = 0.68,
                  max_hits: int = 100) -> list[tuple[int, int]]:
    """Semantic stage 2b: return [(item_id, shop_id)] with cosine ≥ threshold.
    Only uses embeddings generated by the currently selected embedding model.
    Empty list when embeddings are unavailable or nothing matches."""
    default_model = get_default_embedding_model(db) or _MODEL
    qvec = embed_text(term, model=default_model)
    if not qvec:
        return []
    _ensure_cache(db)
    if not _CACHE:
        return []
    qn = _normalize(qvec)
    scored = []
    for item_id, shop_id, vec in _CACHE:
        # both vectors are unit-normalized -> dot product == cosine similarity
        sim = sum(a * b for a, b in zip(qn, vec))
        if sim >= threshold:
            scored.append((sim, item_id, shop_id))
    scored.sort(key=lambda t: -t[0])
    return [(item_id, shop_id) for _sim, item_id, shop_id in scored[:max_hits]]
