"""Web search — grounds concept expansion (agent.expand_concept) in
real-world data so the LLM's own knowledge gap doesn't silently drop items
("chicken biryani ingredients" is a much longer list than most models
volunteer unprompted).

Exa is used when EXA_API_KEY is configured — it's built for exactly this
kind of LLM-grounding use case and returns cleaner, more relevant snippets
than a generic search engine. Falls back to DuckDuckGo (ddgs) — free, no
API key — when Exa isn't configured or a call fails, same graceful-
degradation pattern as the rest of this app.

This is intentionally much smaller than Locus's web_research.py: Myna only
needs a handful of snippets as grounding context for one LLM call, not a
multi-round research-and-synthesis pipeline.
"""

import httpx
from ddgs import DDGS

from .config import EXA_API_KEY

_MAX_RESULTS = 5
_SNIPPET_CHARS = 300
_EXA_URL = "https://api.exa.ai/search"


def _search_exa(query: str, max_results: int) -> list[dict]:
    if not EXA_API_KEY:
        return []
    try:
        resp = httpx.post(
            _EXA_URL,
            headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": max_results,
                "type": "auto",
                "contents": {"text": {"maxCharacters": _SNIPPET_CHARS}},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "snippet": (r.get("text") or "").strip(),
                "url": r.get("url", ""),
            }
            for r in results
        ]
    except Exception:
        return []


def _search_ddg(query: str, max_results: int) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []
    return [
        {"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")}
        for r in results
    ]


def search(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """Web search. Returns [] on total failure — callers must treat results
    as optional grounding, never a hard dependency."""
    if EXA_API_KEY:
        results = _search_exa(query, max_results)
        if results:
            return results
    return _search_ddg(query, max_results)


def ingredient_context(concept: str, max_results: int = _MAX_RESULTS) -> str:
    """Search-and-format helper for agent.expand_concept: a short block of web
    snippets about what's typically included in `concept`, to ground the
    LLM's item list against. Empty string if search fails or returns nothing
    (the caller falls back to the model's own knowledge, as before)."""
    results = search(f"{concept} ingredients list what's needed", max_results=max_results)
    lines = []
    for r in results:
        snippet = " ".join((r.get("snippet") or "").split())[:_SNIPPET_CHARS]
        if snippet:
            lines.append(f"- {snippet}")
    return "\n".join(lines)
