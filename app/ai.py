import base64
import io
import json
import re
from pathlib import Path

import httpx

from .config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    GEMINI_API_KEY,
)

_SIGNAGE_PROMPT = (
    "This is a photo of a shop's signage/name board. "
    "Read the shop name from it. Reply with ONLY the shop name, nothing else. "
    "If you cannot read a name, reply with an empty string."
)

# One photo of a shop shelf, counter or crate usually holds many products, and
# a shopkeeper photographing their stock expects all of them back — not the one
# item that happens to be in focus. So the prompt asks for a JSON list and
# names the categories the app already uses, which keeps the returned
# categories consistent with catalogue-added items instead of freeform.
_ITEMS_PROMPT = (
    "You are helping an Indian kirana shopkeeper list their stock.\n"
    "Look at this photo and identify EVERY distinct product you can see — "
    "packets, bottles, jars, loose produce, sacks, anything on the shelf, "
    "counter or floor. Do not stop at the first product.\n\n"
    "Reply with ONLY a JSON array, no other text, in this shape:\n"
    '[{"name": "Parle-G Gold Biscuits 100g", "category": "Snacks & biscuits"},\n'
    ' {"name": "Tata Salt 1kg", "category": "Everyday grocery"}]\n\n'
    "Rules:\n"
    "- One entry per distinct product. Do not repeat the same product.\n"
    "- Include the brand and the pack size in the name when they are readable.\n"
    "- For loose produce use the common name, e.g. \"Onion (Pyaz)\".\n"
    "- Pick a category from this list where it fits: "
    "Everyday grocery, Dal & pulses, Spices & masala, Puja items, "
    "Dry fruits & nuts, Vegetables, Fruits, Oil & ghee, Dairy bread & eggs, "
    "Snacks & biscuits, Cold drinks & beverages, Cleaning & household, "
    "Personal care, Baby care, Stationery & general, Sweets & bakery.\n"
    "- Guess when a label is partly hidden; a good guess is more useful than "
    "leaving the product out.\n"
    "- If the photo has no products at all, reply with []."
)

# Phone photos run 2-5 MB, and Anthropic rejects a request whose base64 image
# is over 5 MB outright — which used to surface as a bare "no suggestion".
# Nothing is gained above ~1568px on the long edge for any of these models
# either, so every image is re-encoded down before it goes out: fewer failures,
# faster replies, smaller bills.
_MAX_EDGE = 1568
_JPEG_QUALITY = 82


def _image_to_b64(image_path: str) -> tuple[str, str]:
    suffix = Path(image_path).suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    raw = Path(image_path).read_bytes()
    shrunk = _downscale(raw)
    if shrunk is not None:
        raw, media_type = shrunk, "image/jpeg"
    return base64.standard_b64encode(raw).decode("utf-8"), media_type


def _downscale(raw: bytes) -> bytes | None:
    """Re-encode an image down to _MAX_EDGE as JPEG. None if it can't be read.

    Also strips EXIF while honouring its orientation flag, so a portrait phone
    photo doesn't reach the model rotated 90°.
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
        if max(img.size) > _MAX_EDGE:
            img.thumbnail((_MAX_EDGE, _MAX_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return None


# Model families that are known to accept images. Anything not matched here is
# reported as text-only, because the failure mode of guessing wrong is silent:
# a text-only model set as the OCR model just returns nothing for every photo.
_VISION_FAMILIES = (
    "claude-3", "claude-4", "claude-5", "sonnet-4", "sonnet-5", "opus-4", "opus-5",
    "haiku-4", "haiku-5", "gemini-1.5", "gemini-2", "gemini-3", "gemma-3",
    "llama-4", "scout", "maverick", "llava", "pixtral", "gpt-4o", "gpt-4.1",
    "gpt-5", "vision", "vl",
)

# Families that are explicitly text-only even though they look like chat models.
_TEXT_ONLY_MARKERS = ("gpt-oss", "guard", "moderation", "reranker", "rerank")

_NON_CHAT_MARKERS = ("embed", "whisper", "tts", "audio", "speech", "imagen", "veo", "aqa")


def _is_chat_model(model_id: str) -> bool:
    """Exclude models that aren't text-in/text-out chat models at all."""
    mid = model_id.lower()
    return not any(marker in mid for marker in _NON_CHAT_MARKERS)


def supports_vision(model_id: str, meta: dict | None = None) -> bool:
    """Best-effort: can this model be sent an image?

    Providers mostly don't advertise this (only Groq sometimes does, under
    "capabilities"), so this falls back to matching known vision families by
    name. It's a hint for the owner panel — `app/vision_check.py` is what
    actually proves a model reads photos.
    """
    mid = (model_id or "").lower()
    caps = (meta or {}).get("capabilities")
    if isinstance(caps, dict) and "vision" in caps:
        return bool(caps["vision"])
    if any(marker in mid for marker in _TEXT_ONLY_MARKERS):
        return False
    return any(family in mid for family in _VISION_FAMILIES)


def _has_image_support(model: dict) -> bool:
    """Kept for callers that only want listable chat models."""
    return _is_chat_model(model.get("id", ""))


def resolve_model(model_str: str) -> tuple[str, str] | None:
    """Resolve a 'provider:model_id' or 'provider/model_id' string.

    Returns (provider_name, model_id) if the provider is configured,
    otherwise None.
    """
    if not model_str:
        return None
    for sep in (":", "/"):
        if sep in model_str:
            provider, model_id = model_str.split(sep, 1)
            provider = provider.strip()
            model_id = model_id.strip()
            if provider in PROVIDERS and PROVIDERS[provider]["api_key"]:
                return provider, model_id
    return None


def _resolve_effective_model(model: str = "", db_default: str = "") -> tuple[str, str] | None:
    """Resolve explicit/default model settings to (provider, model_id)."""
    resolved = resolve_model(model)
    if resolved:
        return resolved
    effective_default = get_effective_default(db_default)
    return resolve_model(effective_default or "")


# ---------------------------------------------------------------------------
# Vision call implementations
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, model: str, image_path: str, prompt: str, max_tokens: int = 150) -> str:
    b64, media_type = _image_to_b64(image_path)
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    blocks = resp.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def _call_groq(api_key: str, model: str, image_path: str, prompt: str, max_tokens: int = 150) -> str:
    b64, media_type = _image_to_b64(image_path)
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    choices = resp.json().get("choices", [])
    return choices[0]["message"]["content"].strip() if choices else ""


def _call_gemini(api_key: str, model: str, image_path: str, prompt: str, max_tokens: int = 150) -> str:
    b64, media_type = _image_to_b64(image_path)
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": media_type, "data": b64}},
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


# ---------------------------------------------------------------------------
# Text call implementations (used by agentic pipelines, no images)
# ---------------------------------------------------------------------------

def _text_anthropic(api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    blocks = resp.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def _text_groq(api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    choices = resp.json().get("choices", [])
    return choices[0]["message"]["content"].strip() if choices else ""


def _text_gemini(api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


# ---------------------------------------------------------------------------
# Model listing implementations
# ---------------------------------------------------------------------------

def _list_anthropic_models(api_key: str) -> list[dict]:
    resp = httpx.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout=30.0,
    )
    resp.raise_for_status()
    models = resp.json().get("data", [])
    out = []
    for m in models:
        mid = m.get("id", "")
        if not _is_chat_model(mid):
            continue
        out.append({
            "provider": "anthropic",
            "model": mid,
            "label": f"anthropic/{mid}",
            "display_name": m.get("display_name", mid),
            "vision": supports_vision(mid, m),
            "context_window": m.get("context_window"),
            "max_output_tokens": m.get("max_output_tokens"),
            "pricing": m.get("pricing"),          # not provided by API, will be None
        })
    return out


def _list_groq_models(api_key: str) -> list[dict]:
    resp = httpx.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    models = resp.json().get("data", [])
    out = []
    for m in models:
        mid = m.get("id", "")
        if not _is_chat_model(mid):
            continue
        out.append({
            "provider": "groq",
            "model": mid,
            "label": f"groq/{mid}",
            "display_name": mid,
            "vision": supports_vision(mid, m),
            "context_window": m.get("context_window"),
            "max_output_tokens": m.get("max_completion_tokens"),
            "pricing": m.get("pricing"),          # not provided by API
        })
    return out


def _list_gemini_models(api_key: str) -> list[dict]:
    resp = httpx.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        timeout=30.0,
    )
    resp.raise_for_status()
    models = resp.json().get("models", [])
    out = []
    for m in models:
        mid = m.get("name", "").replace("models/", "")
        if not _is_chat_model(mid):
            continue
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        out.append({
            "provider": "gemini",
            "model": mid,
            "label": f"gemini/{mid}",
            "display_name": m.get("displayName", mid),
            "vision": supports_vision(mid, m),
            "context_window": m.get("inputTokenLimit"),
            "max_output_tokens": m.get("outputTokenLimit"),
            "pricing": None,                       # Google doesn't expose this via API
        })
    return out


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

PROVIDERS = {
    "anthropic": {
        "api_key": ANTHROPIC_API_KEY,
        "default_model": "claude-sonnet-4-20250514",
        "call": _call_anthropic,
        "text_call": _text_anthropic,
        "list_models": _list_anthropic_models,
    },
    "groq": {
        "api_key": GROQ_API_KEY,
        "default_model": "llama-3.3-70b-versatile",
        "call": _call_groq,
        "text_call": _text_groq,
        "list_models": _list_groq_models,
    },
    "gemini": {
        "api_key": GEMINI_API_KEY,
        "default_model": "gemini-2.5-flash",
        "call": _call_gemini,
        "text_call": _text_gemini,
        "list_models": _list_gemini_models,
    },
}


def configured_providers() -> list[str]:
    """Return names of providers that have an API key set."""
    return [name for name, p in PROVIDERS.items() if p["api_key"]]


def fetch_all_models() -> list[dict]:
    """Fetch available vision models from all configured providers."""
    all_models = []
    for name, p in PROVIDERS.items():
        if not p["api_key"]:
            continue
        try:
            models = p["list_models"](p["api_key"])
            all_models.extend(models)
        except Exception:
            # If listing fails, offer at least the default model
            all_models.append({
                "provider": name,
                "model": p["default_model"],
                "label": f"{name}/{p['default_model']}",
                "display_name": p["default_model"],
                "vision": supports_vision(p["default_model"]),
                "context_window": None,
                "max_output_tokens": None,
                "pricing": None,
            })
    return all_models


def get_effective_default(db_default: str) -> str | None:
    """Resolve the default model to use. db_default takes priority;
    falls back to first provider's default model if no DB setting.
    Accepts both 'provider/model' and 'provider:model' formats."""
    if db_default:
        for sep in ("/", ":"):
            if sep in db_default:
                provider = db_default.split(sep, 1)[0]
                if provider in PROVIDERS and PROVIDERS[provider]["api_key"]:
                    return db_default
    for name, p in PROVIDERS.items():
        if p["api_key"]:
            return f"{name}/{p['default_model']}"
    return None


def _call_vision_detailed(
    image_path: str,
    prompt: str,
    db_default: str = "",
    model: str = "",
    max_tokens: int = 150,
) -> tuple[str, str]:
    """Route a vision call through the specified or default provider.

    Returns (reply_text, error). Exactly one of the two is meaningful: on
    success error is '', on failure reply_text is ''. The error string is
    short and safe to show a shopkeeper — "no photo model is configured" is a
    very different problem from "the model timed out", and the old
    swallow-everything version made both look like "the AI found nothing".

    model: explicit 'provider:model_id' or 'provider/model_id' string.
    db_default: fallback DB-stored default model string.
    """
    resolved = _resolve_effective_model(model, db_default)
    if not resolved:
        return "", "No AI model is set up for photos yet."
    provider_name, model_id = resolved
    provider = PROVIDERS.get(provider_name)
    if not provider or not provider["api_key"]:
        return "", f"The {provider_name} API key is missing."
    if not supports_vision(model_id):
        return "", f"{model_id} can't read photos. Pick a vision model in the owner panel."
    try:
        return provider["call"](provider["api_key"], model_id, image_path, prompt, max_tokens), ""
    except httpx.TimeoutException:
        return "", "The AI took too long to answer. Please try again."
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            return "", f"The {provider_name} API key was rejected."
        if code == 429:
            return "", "The AI is rate-limited right now. Please try again in a moment."
        return "", f"The AI service returned an error ({code})."
    except Exception:
        return "", "Could not reach the AI service."


def _call_vision(image_path: str, prompt: str, db_default: str = "", model: str = "",
                 max_tokens: int = 150) -> str:
    """Text-only wrapper over _call_vision_detailed. '' on any failure."""
    text, _ = _call_vision_detailed(image_path, prompt, db_default, model, max_tokens)
    return text


def _parse_items(text: str) -> list[dict]:
    """Pull a list of {name, category} out of a vision model's reply.

    Models drift: some return bare JSON, some fence it in ```json, some ignore
    the format and write "Tata Salt 1kg | Grocery" a line at a time. All three
    are worth accepting — the shopkeeper doesn't care which model is behind
    the button, only that their shelf photo turned into a list.
    """
    if not text:
        return []
    out: list[dict] = []

    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    array = re.search(r"\[.*\]", candidate, re.S)
    if array:
        try:
            data = json.loads(array.group(0))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    name = str(entry.get("name") or entry.get("item") or "").strip()
                    category = str(entry.get("category") or "").strip()
                elif isinstance(entry, str):
                    name, category = entry.strip(), ""
                else:
                    continue
                if name:
                    out.append({"name": name, "category": category})

    if not out:
        # Line-oriented fallback: "name | category", one per line, tolerating
        # bullets and numbering.
        for line in text.splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if not line or line.startswith(("```", "[", "]", "{")):
                continue
            name, _, category = line.partition("|")
            name = name.strip().strip('"')
            if name:
                out.append({"name": name, "category": category.strip().strip('",')})

    # Same product photographed twice in one frame is one line in the shop's
    # list, so fold case-insensitive duplicates while keeping the first
    # spelling the model gave.
    deduped: list[dict] = []
    seen: set[str] = set()
    for entry in out:
        key = entry["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped[:40]


# ---------------------------------------------------------------------------
# Public API (called from routers — pass db_default to honour saved setting)
# ---------------------------------------------------------------------------

def call_text(prompt: str, db_default: str = "", max_tokens: int = 300, model: str = "") -> str:
    """Route a plain-text LLM call through the specified or default provider.
    Returns '' on failure.

    model: explicit 'provider:model_id' or 'provider/model_id' string.
    db_default: fallback DB-stored default model string.
    """
    resolved = _resolve_effective_model(model, db_default)
    if not resolved:
        return ""
    provider_name, model_id = resolved
    provider = PROVIDERS.get(provider_name)
    if not provider or not provider["api_key"]:
        return ""
    try:
        return provider["text_call"](provider["api_key"], model_id, prompt, max_tokens)
    except Exception:
        return ""


def suggest_shop_name(image_path: str, db_default: str = "", model: str = "") -> str:
    return _call_vision(image_path, _SIGNAGE_PROMPT, db_default, model=model)


def suggest_shop_name_detailed(image_path: str, db_default: str = "", model: str = "") -> tuple[str, str]:
    """suggest_shop_name plus the reason it failed. Returns (name, error)."""
    name, error = _call_vision_detailed(image_path, _SIGNAGE_PROMPT, db_default, model=model)
    if error:
        return "", error
    if not name.strip():
        return "", "Couldn't read the board. Try a straighter, brighter photo."
    return name.strip(), ""


def suggest_items(image_path: str, db_default: str = "", model: str = "") -> tuple[list[dict], str]:
    """Identify every product in a photo.

    Returns (items, error) where items is a list of {"name", "category"} in
    the order the model saw them. A generous token budget matters here: a
    shelf photo can easily be twenty products, and a reply truncated mid-JSON
    parses as nothing at all.
    """
    text, error = _call_vision_detailed(
        image_path, _ITEMS_PROMPT, db_default, model=model, max_tokens=1500
    )
    if error:
        return [], error
    items = _parse_items(text)
    if not items:
        return [], "Couldn't spot any products in that photo. Try a closer, brighter shot."
    return items, ""


def suggest_item(image_path: str, db_default: str = "", model: str = "") -> tuple[str, str]:
    """Single-item view of suggest_items — returns (name, category)."""
    items, _ = suggest_items(image_path, db_default, model=model)
    if not items:
        return "", ""
    return items[0]["name"], items[0]["category"]


# ---------------------------------------------------------------------------
# One-photo add: read a whole food vendor off a single picture
# ---------------------------------------------------------------------------
# The reason the add flow can be one photo at all is that a food thela's board
# *is* its inventory — "CHOWMEIN 40 / MOMOS 50 / SPRING ROLL 60" is the shop
# name, the menu and the price list in one frame. So this asks for all of it in
# a single call instead of making someone photograph a board and then type a
# menu.

def _board_prompt() -> str:
    from . import food
    kinds = ", ".join(food.KIND_ORDER)
    categories = ", ".join(food.CATEGORY_NAMES)
    return (
        "This is a photo of an Indian street-food vendor — a thela/cart, chaat "
        "corner, chai tapri, dhaba or small eatery. Read everything you can.\n\n"
        "Reply with ONLY a JSON object, no other text, in this shape:\n"
        '{"name": "Sharma Chinese Corner",\n'
        ' "kind": "chinese",\n'
        ' "items": [{"name": "Chowmein", "price": 40, "category": "Chinese"},\n'
        '           {"name": "Veg Momos", "price": 50, "category": "Chinese"}]}\n\n'
        "Rules:\n"
        "- name: the vendor's name from the board. If there is no name written, "
        "build a short descriptive one from what they sell, e.g. \"Momos thela\".\n"
        f"- kind: exactly one of: {kinds}.\n"
        "- items: EVERY dish/drink you can see on the menu board, on the tawa, in "
        "the trays, or written anywhere. Do not stop at the first one.\n"
        "- price: the number in rupees if it is written next to the dish, "
        "otherwise 0. Never invent a price.\n"
        f"- category: pick from this list: {categories}.\n"
        "- Use the common Hinglish dish name people say out loud (\"Chole "
        "Bhature\", \"Golgappe\", \"Chowmein\"), not a translated English one.\n"
        "- Guess when the board is blurry or partly hidden; a good guess is more "
        "useful than leaving a dish out.\n"
        "- If this is not a food vendor at all, reply "
        '{"name": "", "kind": "other", "items": []}.'
    )


def _parse_board(text: str) -> dict:
    """Pull {name, kind, items[]} out of a vision model's reply.

    Falls back hard: if the object won't parse, the item-list parser still gets
    a shot at the same text, because a menu read with no shop name is worth far
    more than nothing at all.
    """
    from . import food

    result = {"name": "", "kind": food.DEFAULT_KIND, "items": []}
    if not text:
        return result

    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    obj = re.search(r"\{.*\}", candidate, re.S)
    data = None
    if obj:
        try:
            data = json.loads(obj.group(0))
        except json.JSONDecodeError:
            data = None

    raw_items: list = []
    if isinstance(data, dict):
        result["name"] = str(data.get("name") or "").strip()
        result["kind"] = food.normalise_kind(data.get("kind"))
        raw_items = data.get("items") or []
    if not isinstance(raw_items, list) or not raw_items:
        # Object didn't parse (or carried no menu) — try the array parser, which
        # tolerates fenced JSON, bare arrays and "name | category" lines.
        raw_items = _parse_items(text)

    seen: set[str] = set()
    for entry in raw_items:
        if isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("item") or "").strip()
            price = _parse_price(entry.get("price"))
            category = str(entry.get("category") or "").strip()
        elif isinstance(entry, str):
            name, price, category = entry.strip(), 0.0, ""
        else:
            continue
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        result["items"].append({
            "name": name,
            "price": price,
            "category": food.normalise_category(category, name),
        })

    if not result["kind"] or result["kind"] == food.DEFAULT_KIND:
        # No usable kind from the model: infer it from the menu instead, which
        # is a better signal than the board's wording anyway.
        joined = " ".join(i["name"] for i in result["items"]).lower()
        if joined:
            result["kind"] = food.normalise_kind(joined)

    result["items"] = result["items"][:40]
    return result


def _parse_price(value) -> float:
    """"₹40", "40/-", "Rs 40", 40 → 40.0. Anything unreadable → 0.0."""
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else 0.0
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return 0.0
    try:
        price = float(match.group(0))
    except ValueError:
        return 0.0
    return price if price > 0 else 0.0


def correct_food_query(terms: list[str], known: list[str], db_default: str = "",
                       model: str = "") -> dict[str, str]:
    """Ask the model what a mistyped dish name was meant to be.

    Only called for terms that nothing local could match — fuzzy matching
    against the vocabulary is free and handles most typos, so paying for an
    LLM call on every search would be waste. This is the last resort, for the
    spellings edit distance can't reach: "chowmin" is easy, "chaomen" or
    "gol gappay" less so.

    Returns {original: corrected} for the ones it was confident about, and
    leaves everything else out — a wrong correction is worse than none,
    because it silently searches for a different food.
    """
    if not terms:
        return {}
    prompt = (
        "An Indian street-food app user typed these search words, possibly "
        "misspelled or transliterated differently:\n"
        f"{', '.join(terms)}\n\n"
        "Here are dish names the app knows:\n"
        f"{', '.join(sorted(known)[:200])}\n\n"
        "For each typed word that is clearly a misspelling of a known dish, "
        "give the known spelling. Reply with ONLY a JSON object, e.g.\n"
        '{"chaomen": "chowmein", "gol gappay": "golgappe"}\n\n'
        "Rules:\n"
        "- Leave a word out entirely if you are not confident.\n"
        "- Leave it out if it is already spelled correctly.\n"
        "- Never invent a dish that is not in the list above.\n"
        "- Reply {} if nothing needs correcting."
    )
    reply = call_text(prompt, db_default, max_tokens=300, model=model)
    if not reply:
        return {}
    match = re.search(r"\{.*\}", reply, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    lowered = {k.lower() for k in known}
    out: dict[str, str] = {}
    for typed, fixed in data.items():
        typed, fixed = str(typed).strip().lower(), str(fixed).strip().lower()
        # The model is only allowed to map onto dishes the app actually knows;
        # anything else is a hallucinated dish and gets dropped.
        if typed and fixed and typed != fixed and fixed in lowered:
            out[typed] = fixed
    return out


def merge_boards(boards: list[dict]) -> dict:
    """Fold several photos of the same vendor into one listing.

    Two photos of one thela carry different halves of the truth: a wide shot
    gets the signboard name, a close one gets the rates, and a shot of the tawa
    gets dishes that were never written down anywhere. Merging is what makes
    taking a second photo worth the extra tap.

    - name: the first non-empty one. Predictable beats clever here — the UI
      tells people to shoot the board first, and a "longest wins" rule would
      happily pick an invented "Momos thela" over a real "Raju".
    - kind: the most common real kind across photos; ties go to the earliest.
    - items: the union. A duplicate dish keeps whichever copy carries a price,
      so the close-up's ₹40 survives the wide shot's priceless entry.
    """
    from . import food

    merged = {"name": "", "kind": food.DEFAULT_KIND, "items": []}
    by_name: dict[str, dict] = {}
    kind_votes: dict[str, int] = {}

    for board in boards:
        if not merged["name"] and board.get("name"):
            merged["name"] = board["name"]
        kind = board.get("kind") or food.DEFAULT_KIND
        if kind != food.DEFAULT_KIND:
            kind_votes[kind] = kind_votes.get(kind, 0) + 1
        for item in board.get("items") or []:
            key = item["name"].strip().lower()
            if not key:
                continue
            existing = by_name.get(key)
            if existing is None:
                by_name[key] = dict(item)
            elif not existing.get("price") and item.get("price"):
                existing["price"] = item["price"]

    if kind_votes:
        merged["kind"] = max(kind_votes, key=lambda k: kind_votes[k])
    merged["items"] = list(by_name.values())[:60]
    if merged["kind"] == food.DEFAULT_KIND and merged["items"]:
        merged["kind"] = food.normalise_kind(" ".join(i["name"] for i in merged["items"]))
    return merged


def read_food_boards(
    image_paths: list[str], db_default: str = "", model: str = ""
) -> tuple[dict, str]:
    """read_food_board over several photos of one vendor, merged.

    An error is only returned when *nothing* was read from *any* photo. One
    unreadable shot among several is not a failure — it's the reason someone
    took more than one.
    """
    boards, errors = [], []
    for path in image_paths:
        board, error = read_food_board(path, db_default, model=model)
        boards.append(board)
        if error:
            errors.append(error)

    merged = merge_boards(boards)
    if merged["name"] or merged["items"]:
        return merged, ""
    return merged, errors[0] if errors else (
        "Photo se kuch samajh nahi aaya. Thoda paas se, roshni mein try karo."
    )


def read_food_board(image_path: str, db_default: str = "", model: str = "") -> tuple[dict, str]:
    """One photo → {name, kind, items:[{name, price, category}]}.

    Returns (board, error). On a partial read — a menu with no legible shop
    name, say — this still returns what it got and no error: the add flow can
    fill a name in itself, and throwing away a read menu to demand a retake is
    exactly the friction this flow exists to remove.
    """
    text, error = _call_vision_detailed(
        image_path, _board_prompt(), db_default, model=model, max_tokens=1500
    )
    if error:
        return _parse_board(""), error
    board = _parse_board(text)
    if not board["name"] and not board["items"]:
        return board, "Photo se kuch samajh nahi aaya. Thoda paas se, roshni mein try karo."
    return board, ""
