import base64
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

_ITEM_PROMPT = (
    "This is a photo of a product in a shop. "
    "Reply with a short product name and category in exactly this format: "
    "name | category\n"
    "Example: Parle-G Gold Biscuits 100g | Snacks\n"
    "Keep the name concise (include brand and size if visible). "
    "If unsure, give your best guess."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _image_to_b64(image_path: str) -> tuple[str, str]:
    suffix = Path(image_path).suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    b64 = base64.standard_b64encode(Path(image_path).read_bytes()).decode("utf-8")
    return b64, media_type


def _has_image_support(model: dict) -> bool:
    """Heuristic: skip text-only / embedding / audio-only models."""
    mid = model.get("id", "").lower()
    if any(x in mid for x in ("embed", "whisper", "tts", "audio", "speech")):
        return False
    # Groq exposes capabilities under "capabilities"; Anthropic/Gemini don't
    caps = model.get("capabilities")
    if caps and isinstance(caps, dict):
        if not caps.get("vision", True):
            return False
    return True


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


# ---------------------------------------------------------------------------
# Vision call implementations
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, model: str, image_path: str, prompt: str) -> str:
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
            "max_tokens": 150,
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


def _call_groq(api_key: str, model: str, image_path: str, prompt: str) -> str:
    b64, media_type = _image_to_b64(image_path)
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 150,
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


def _call_gemini(api_key: str, model: str, image_path: str, prompt: str) -> str:
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
            "generationConfig": {"maxOutputTokens": 150},
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
        if not _has_image_support(m):
            continue
        out.append({
            "provider": "anthropic",
            "model": mid,
            "label": f"anthropic/{mid}",
            "display_name": m.get("display_name", mid),
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
        if not _has_image_support(m):
            continue
        caps = m.get("capabilities") or {}
        out.append({
            "provider": "groq",
            "model": mid,
            "label": f"groq/{mid}",
            "display_name": mid,
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
        if not _has_image_support(m):
            continue
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        out.append({
            "provider": "gemini",
            "model": mid,
            "label": f"gemini/{mid}",
            "display_name": m.get("displayName", mid),
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
        "default_model": "meta-llama/llama-4-scout-17b-16e-instruct",
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


def _call_vision(image_path: str, prompt: str, db_default: str = "", model: str = "") -> str:
    """Route a vision call through the specified or default provider.
    Returns '' on failure.

    model: explicit 'provider:model_id' or 'provider/model_id' string.
    db_default: fallback DB-stored default model string.
    """
    effective = resolve_model(model) or get_effective_default(db_default)
    if not effective:
        return ""
    if "/" in effective:
        provider_name, model_id = effective.split("/", 1)
    else:
        provider_name, model_id = effective.split(":", 1)
    provider = PROVIDERS.get(provider_name)
    if not provider or not provider["api_key"]:
        return ""
    try:
        return provider["call"](provider["api_key"], model_id, image_path, prompt)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public API (called from routers — pass db_default to honour saved setting)
# ---------------------------------------------------------------------------

def call_text(prompt: str, db_default: str = "", max_tokens: int = 300, model: str = "") -> str:
    """Route a plain-text LLM call through the specified or default provider.
    Returns '' on failure.

    model: explicit 'provider:model_id' or 'provider/model_id' string.
    db_default: fallback DB-stored default model string.
    """
    effective = resolve_model(model) or get_effective_default(db_default)
    if not effective:
        return ""
    if "/" in effective:
        provider_name, model_id = effective.split("/", 1)
    else:
        provider_name, model_id = effective.split(":", 1)
    provider = PROVIDERS.get(provider_name)
    if not provider or not provider["api_key"]:
        return ""
    try:
        return provider["text_call"](provider["api_key"], model_id, prompt, max_tokens)
    except Exception:
        return ""


def suggest_shop_name(image_path: str, db_default: str = "", model: str = "") -> str:
    return _call_vision(image_path, _SIGNAGE_PROMPT, db_default, model=model)


def suggest_item(image_path: str, db_default: str = "", model: str = "") -> tuple[str, str]:
    """Returns (name, category). Either may be empty on failure."""
    text = _call_vision(image_path, _ITEM_PROMPT, db_default, model=model)
    if "|" in text:
        name, _, category = text.partition("|")
        return name.strip(), category.strip()
    return text.strip(), ""
