"""Lightweight web search — grounds concept expansion (agent.expand_concept)
in real-world data so the LLM's own knowledge gap doesn't silently drop
items ("chicken biryani ingredients" is a much longer list than most models
volunteer unprompted). Uses DuckDuckGo via ddgs — free, no API key, same
choice Locus makes for its web research.

This is intentionally much smaller than Locus's web_research.py: Myna only
needs a handful of snippets as grounding context for one LLM call, not a
multi-round research-and-synthesis pipeline.
"""

from ddgs import DDGS

_MAX_RESULTS = 5
_SNIPPET_CHARS = 300


def search(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """Plain web search. Returns [] on any failure (network, rate limit,
    ddgs unavailable) — callers must treat results as optional grounding,
    never a hard dependency."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []
    return [
        {"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")}
        for r in results
    ]


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
