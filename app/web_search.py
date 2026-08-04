"""Web search — a small grounding utility, kept for features not built yet.

Nothing calls this today. It's here on purpose, for the things it's meant to
feed later:

- **Trending** — what people are actually eating this week, so the home screen
  can lead with it instead of a fixed chip list.
- **Weather-based suggestions** — barish ho rahi hai to pakode aur chai, garmi
  me shikanji, lassi, ice cream.

Both need real-world signal the model doesn't carry on its own, which is what
this is for. Keeping an untested module around is how it quietly rots, so the
result-shaping logic is covered in `test_smoke.py` against fake backends —
enough to catch a provider changing its response shape without the tests
needing network access.

Exa is used when `EXA_API_KEY` is configured — it's built for LLM grounding
and returns cleaner snippets than a generic engine. Falls back to DuckDuckGo
(`ddgs`) — free, no API key — when Exa isn't configured or a call fails, the
same graceful-degradation pattern as the rest of this app. Callers must treat
results as optional: this returns `[]` rather than raising, always.
"""

import httpx

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
    # Imported here rather than at module scope so a missing `ddgs` install
    # degrades to "no results" instead of breaking the whole app at import.
    try:
        from ddgs import DDGS
    except ImportError:
        return []
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
    """Web search. Returns a list of {title, snippet, url}, or [] on failure.

    Exa first when configured, DuckDuckGo otherwise — and DuckDuckGo also
    catches the case where Exa is configured but returns nothing.
    """
    if EXA_API_KEY:
        results = _search_exa(query, max_results)
        if results:
            return results
    return _search_ddg(query, max_results)


def context_block(query: str, max_results: int = _MAX_RESULTS) -> str:
    """Search results as a plain block of lines, ready to paste into a prompt.

    Whitespace is collapsed and each snippet is truncated, because what goes
    into an LLM prompt should be short and uniform — a raw page dump costs
    tokens and buries the signal. Empty string when there's nothing, so a
    caller can drop the grounding section entirely rather than send a header
    with nothing under it.
    """
    lines = []
    for result in search(query, max_results=max_results):
        snippet = " ".join((result.get("snippet") or "").split())[:_SNIPPET_CHARS]
        if snippet:
            lines.append(f"- {snippet}")
    return "\n".join(lines)
