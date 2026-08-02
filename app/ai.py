import base64
from pathlib import Path

import httpx

from .config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    GEMINI_API_KEY,
    MYNA_DEFAULT_MODEL,
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
# Provider registry — each entry knows how to make a vision call.
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


# Each provider:  env key, default model, and the call function.
PROVIDERS = {
    "anthropic": {
        "api_key": ANTHROPIC_API_KEY,
        "default_model": "claude-sonnet-4-20250514",
        "call": _call_anthropic,
    },
    "groq": {
        "api_key": GROQ_API_KEY,
        "default_model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "call": _call_groq,
    },
    "gemini": {
        "api_key": GEMINI_API_KEY,
        "default_model": "gemini-2.5-flash",
        "call": _call_gemini,
    },
}


def configured_providers() -> list[str]:
    """Return names of providers that have an API key set."""
    return [name for name, p in PROVIDERS.items() if p["api_key"]]


def get_default_model() -> str | None:
    """Return the 'provider/model' string to use, or None if nothing configured."""
    if MYNA_DEFAULT_MODEL:
        provider = MYNA_DEFAULT_MODEL.split("/", 1)[0]
        if provider in PROVIDERS and PROVIDERS[provider]["api_key"]:
            return MYNA_DEFAULT_MODEL
    # Fall back to first configured provider with its default model
    for name, p in PROVIDERS.items():
        if p["api_key"]:
            return f"{name}/{p['default_model']}"
    return None


def list_models() -> list[dict]:
    """All available models across configured providers."""
    out = []
    for name, p in PROVIDERS.items():
        if not p["api_key"]:
            continue
        out.append({
            "provider": name,
            "model": p["default_model"],
            "label": f"{name}/{p['default_model']}",
        })
    return out


def _call_vision(image_path: str, prompt: str) -> str:
    """Route a vision call through the default provider. Returns '' on failure."""
    default = get_default_model()
    if not default:
        return ""
    provider_name, model = default.split("/", 1)
    provider = PROVIDERS[provider_name]
    try:
        return provider["call"](provider["api_key"], model, image_path, prompt)
    except Exception:
        return ""


def suggest_shop_name(image_path: str) -> str:
    return _call_vision(image_path, _SIGNAGE_PROMPT)


def suggest_item(image_path: str) -> tuple[str, str]:
    """Returns (name, category). Either may be empty on failure."""
    text = _call_vision(image_path, _ITEM_PROMPT)
    if "|" in text:
        name, _, category = text.partition("|")
        return name.strip(), category.strip()
    return text.strip(), ""
