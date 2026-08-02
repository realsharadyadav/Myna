"""Semantic search embeddings.

Two backends, selectable per-deployment from the admin panel:
  - local (default): BAAI/bge-small-en-v1.5 via fastembed, running in-process —
    no API key, no network call, works out of the box. Falls back to a
    deterministic hashing-trick vector (literal token overlap only, no real
    semantics) if fastembed isn't installed or fails to load, so semantic
    search always produces *something* rather than nothing.
  - gemini: Google's text-embedding-004 via the Gemini API — opt-in, requires
    GEMINI_API_KEY.

Vectors are stored as a JSON string on items.embedding, tagged with
items.embedding_model so vectors from different models never get compared
against each other. At pilot scale (~thousands of items) brute-force cosine
similarity in Python takes single-digit milliseconds, so no vector DB is
needed. Swap for pgvector/sqlite-vec if the catalogue grows past ~50k items.

An in-process cache avoids re-reading/parsing every item row on each search.
Invalidate via invalidate_cache() whenever items change.
"""

import hashlib
import importlib.util
import json
import math
import re

import httpx
from sqlalchemy.orm import Session

from .config import GEMINI_API_KEY
from .database import get_default_embedding_model

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

FASTEMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
LOCAL_MODEL = f"local/{FASTEMBED_MODEL_NAME}"
HASH_MODEL = "local/hash-fallback-v1"
GEMINI_MODEL_ID = "text-embedding-004"
GEMINI_MODEL = f"gemini/{GEMINI_MODEL_ID}"
DEFAULT_MODEL = LOCAL_MODEL

_GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:embedContent"
_GEMINI_BATCH_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:batchEmbedContents"

# Flipped to False permanently after the first Gemini network/auth failure, so
# a bad GEMINI_API_KEY doesn't spam the API on every search.
_gemini_ok = True

_FASTEMBED_INSTALLED = importlib.util.find_spec("fastembed") is not None
_fastembed_model = None
_fastembed_load_failed = False

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")

# (item_id, shop_id, unit-normalized vector), populated by _ensure_cache().
_CACHE: list[tuple[int, int, tuple[float, ...]]] | None = None


def enabled() -> bool:
    """Semantic search always has a working backend: local embeddings need
    no API key or network access."""
    return True


def _mark_gemini_failed() -> None:
    global _gemini_ok
    _gemini_ok = False


def _normalize(vec: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


# ---------------------------------------------------------------------------
# Local backend — fastembed (BAAI/bge-small-en-v1.5), hashing-trick fallback
# ---------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_PATTERN.findall(text)]


def _hash_embed(text: str) -> list[float]:
    """Deterministic hashing-trick vector. No semantic meaning — only literal
    token overlap. Used only when fastembed is unavailable or fails to load."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return list(_normalize(vector))


def _get_fastembed_model():
    global _fastembed_model, _fastembed_load_failed
    if not _FASTEMBED_INSTALLED or _fastembed_load_failed:
        return None
    if _fastembed_model is None:
        try:
            from fastembed import TextEmbedding
            _fastembed_model = TextEmbedding(model_name=FASTEMBED_MODEL_NAME)
        except Exception:
            _fastembed_load_failed = True
            return None
    return _fastembed_model


def active_local_model() -> str:
    """The local embedding scheme actually usable right now, verified by
    loading the model rather than just checking whether the package is
    installed."""
    return LOCAL_MODEL if _get_fastembed_model() is not None else HASH_MODEL


def _local_embed_passages(texts: list[str]) -> list[list[float]]:
    model = _get_fastembed_model()
    if model is not None:
        try:
            return [list(_normalize([float(x) for x in v])) for v in model.passage_embed(texts)]
        except Exception:
            pass
    return [_hash_embed(t) for t in texts]


def _local_embed_query(text: str) -> list[float]:
    """Asymmetric query-side embedding — bge models expect a different
    representation for queries vs passages."""
    model = _get_fastembed_model()
    if model is not None:
        try:
            vec = next(iter(model.query_embed([text])))
            return list(_normalize([float(x) for x in vec]))
        except Exception:
            pass
    return _hash_embed(text)


# ---------------------------------------------------------------------------
# Cloud backend — Gemini text-embedding-004
# ---------------------------------------------------------------------------

def _gemini_embed(text: str, task_type: str) -> list[float] | None:
    if not GEMINI_API_KEY or not _gemini_ok or not text.strip():
        return None
    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={
                "model": f"models/{GEMINI_MODEL_ID}",
                "content": {"parts": [{"text": text.strip()[:2000]}]},
                "taskType": task_type,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        values = resp.json().get("embedding", {}).get("values")
        return list(values) if values else None
    except Exception:
        _mark_gemini_failed()
        return None


def _gemini_embed_batch(texts: list[str], task_type: str) -> list[list[float] | None]:
    if not GEMINI_API_KEY or not _gemini_ok or not texts:
        return [None] * len(texts)
    try:
        resp = httpx.post(
            _GEMINI_BATCH_URL,
            params={"key": GEMINI_API_KEY},
            json={"requests": [
                {"model": f"models/{GEMINI_MODEL_ID}",
                 "content": {"parts": [{"text": t.strip()[:2000]}]},
                 "taskType": task_type}
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
        _mark_gemini_failed()
        return [None] * len(texts)


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------

def _is_gemini(model: str) -> bool:
    return model.startswith("gemini/") or model.startswith("gemini:")


def embed_passages(texts: list[str], model: str = "") -> list[list[float] | None]:
    """Embed document/item text for indexing (batch). Local entries always
    succeed (hash fallback); Gemini entries are None on failure so a caller
    never mixes an unrelated model's vector into a Gemini-tagged item."""
    if not texts:
        return []
    if _is_gemini(model):
        return _gemini_embed_batch(texts, "RETRIEVAL_DOCUMENT")
    return _local_embed_passages(texts)


def embed_query(text: str, model: str = "") -> list[float] | None:
    """Embed a search query (single)."""
    if not text.strip():
        return None
    if _is_gemini(model):
        return _gemini_embed(text, "RETRIEVAL_QUERY")
    return _local_embed_query(text)


def fetch_embedding_models() -> list[dict]:
    """Embedding models selectable from the admin panel."""
    out = [{
        "provider": "local",
        "model": FASTEMBED_MODEL_NAME,
        "label": LOCAL_MODEL,
        "display_name": (
            "Local — BAAI/bge-small-en-v1.5 (offline, default)"
            if _FASTEMBED_INSTALLED
            else "Local — hashing fallback (offline, no real semantics)"
        ),
    }]
    if GEMINI_API_KEY:
        out.append({
            "provider": "gemini",
            "model": GEMINI_MODEL_ID,
            "label": GEMINI_MODEL,
            "display_name": "Gemini text-embedding-004 (cloud API)",
        })
    return out


# ---------------------------------------------------------------------------
# Item embedding / cache / search
# ---------------------------------------------------------------------------

def item_text(item) -> str:
    """The text we embed for an item — name plus category for context."""
    return f"{item.name} — {item.category}" if item.category else item.name


def _effective_model(db=None) -> str:
    if db is not None:
        configured = get_default_embedding_model(db)
        if configured:
            return configured
    return DEFAULT_MODEL


def _stored_model_tag(model: str) -> str:
    """The concrete model tag to persist on items — resolves the local
    scheme to whichever backend actually ran (fastembed vs hash fallback)."""
    return GEMINI_MODEL if _is_gemini(model) else active_local_model()


def embed_item(item, db=None) -> None:
    """(Re)generate and store one item's embedding in place."""
    model = _effective_model(db)
    vec = embed_passages([item_text(item)], model=model)[0]
    if vec:
        item.embedding = json.dumps(vec)
        item.embedding_model = _stored_model_tag(model)


def embed_items(items: list, db=None) -> None:
    """(Re)generate embeddings for several items in one batched pass.

    Bulk-adding a whole category is dozens of items at once; embedding them
    one at a time would mean dozens of round trips on the Gemini backend and
    dozens of separate fastembed calls locally.
    """
    if not items:
        return
    model = _effective_model(db)
    stored_tag = _stored_model_tag(model)
    vectors = embed_passages([item_text(it) for it in items], model=model)
    for item, vec in zip(items, vectors):
        if vec:
            item.embedding = json.dumps(vec)
            item.embedding_model = stored_tag


def backfill(db: Session, batch_size: int = 100) -> int:
    """Embed every item that doesn't have a vector yet, or whose
    embedding_model doesn't match the current default. Returns count embedded."""
    from . import models
    model = _effective_model(db)
    stored_tag = _stored_model_tag(model)
    pending = (
        db.query(models.Item)
        .filter(
            (models.Item.embedding == "") | (models.Item.embedding.is_(None)) |
            (models.Item.embedding_model != stored_tag)
        )
        .all()
    )
    done = 0
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        vectors = embed_passages([item_text(it) for it in batch], model=model)
        for item, vec in zip(batch, vectors):
            if vec:
                item.embedding = json.dumps(vec)
                item.embedding_model = stored_tag
                done += 1
        db.commit()
    if done:
        invalidate_cache()
    return done


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


def _ensure_cache(db: Session) -> None:
    global _CACHE
    if _CACHE is not None:
        return
    from . import models
    stored_tag = _stored_model_tag(_effective_model(db))
    cache: list[tuple[int, int, tuple[float, ...]]] = []
    rows = (
        db.query(models.Item)
        .filter(
            models.Item.embedding != "",
            models.Item.embedding.isnot(None),
            models.Item.embedding_model == stored_tag,
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
    _CACHE = cache


def similar_items(db: Session, term: str, threshold: float = 0.68,
                  max_hits: int = 100) -> list[tuple[int, int]]:
    """Semantic stage 2b: return [(item_id, shop_id)] with cosine ≥ threshold.
    Only uses embeddings generated by the currently selected embedding model.
    Empty list when nothing matches."""
    model = _effective_model(db)
    qvec = embed_query(term, model=model)
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
