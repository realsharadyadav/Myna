"""Agentic search pipeline.

Stage 1 — Query understanding: split a free-form query ("salt milk and mango",
"kala namak, doodh 1L") into individual shopping items. Uses the configured
LLM provider (fast, handles Hinglish/synonyms); falls back to a rule-based
split on commas / 'and' / '&' / '+' when no provider is configured or the
LLM call fails — so search keeps working without any API key.

Stage 2 (in routers/search.py) — Retrieval: run the existing fuzzy matcher
for every parsed item.

Stage 3 (in routers/search.py) — Aggregation: group hits per shop, compute
how many of the requested items each shop covers, and rank shops by
coverage (most items found first), then distance (nearest first).
"""

import json
import re

from . import ai

_PARSE_PROMPT = """You are the query-understanding stage of a hyperlocal grocery search engine.
Extract the individual items the user wants to buy from their query.

Rules:
- Split compound requests like "salt milk and mango" into separate items: ["salt","milk","mango"]
- Drop quantities, sizes and units ("doodh 1 litre" -> "doodh", "att kom" -> "att")
- Keep multi-word product names together ("toor dal", "olive oil", "amul milk")
- Understand Hindi/Hinglish: "namak" -> "namak" (keep the user's word, do not translate)
- If the query is a single item, return a one-element list
- Correct obvious typos ("suger" -> "sugar")

Reply with ONLY a JSON array of lowercase strings, e.g. ["salt","milk","mango"]
Query: "{query}\""""

_SPLIT_RE = re.compile(r"\s*(?:,|&|\+|;|/|\band\b|\naur\b)\s*", re.IGNORECASE)
_FILLER_RE = re.compile(
    r"\b(i|we|want|need|buy|get|please|show|find|me|some|a|an|the|chahiye|karna|karo)\b",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:kg|g|gm|gms|gram|grams|l|lt|ltr|litre|liter|litres|liters|ml|"
    r"pack|packs|packet|packets|pc|pcs|piece|pieces|dozen|kilo)\b",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _clean_item(text: str) -> str:
    """Strip quantities and filler words from a candidate item phrase."""
    text = _QUANTITY_RE.sub(" ", text)
    text = _FILLER_RE.sub(" ", text)
    text = re.sub(r"[^a-zA-Z\u0900-\u097F\s\-]", " ", text)  # keep letters (incl. Devanagari)
    text = re.sub(r"\s+", " ", text).strip(" -").lower()
    return text


def _fallback_parse(query: str) -> list[str]:
    """Rule-based splitter used when no LLM is available."""

    def _split_head(head: str) -> list[str]:
        """Words before a connector: a 3+-word head likely means a missing
        comma ("salt milk and mango"), so split into single items; short
        heads stay together ("amul milk", "groundnut oil")."""
        words = [_clean_item(w) for w in head.split()]
        words = [w for w in words if w]
        if len(words) > 2:
            return words
        return [_clean_item(head)] if _clean_item(head) else []

    def _split_phrase(phrase: str, allow_head_split: bool) -> list[str]:
        prefix = phrase.split()[0] if phrase.split() else ""
        # Prefix likely quantifies the next item ("2kg" in "2kg salt") — the
        # quantity belongs to the following phrase, so don't attach it here.
        skip_first = bool(_BARE_NUMBER_RE.match(prefix) or _QUANTITY_RE.fullmatch(prefix))
        for connector in (" and ", " aur "):
            idx = phrase.lower().find(connector)
            if idx > 0:
                head = phrase[:idx].strip()
                tail = phrase[idx + len(connector):]
                head_items = _split_head(head) if allow_head_split else [_clean_item(head)]
                return head_items + _fallback_parse(tail)
        if skip_first:
            rest = " ".join(phrase.split()[1:])
            return [_clean_item(rest)] if len(rest.split()) <= 2 else _split_head(rest)
        if len(phrase.split()) > 2 and allow_head_split:
            return _split_head(phrase)
        return [_clean_item(phrase)]

    items: list[str] = []
    parts = [p.strip() for p in _SPLIT_RE.split(query or "") if p.strip()]
    allow_head_split = len(parts) > 1  # multi-part query => treat as shopping list
    for part in parts:
        for item in _split_phrase(part, allow_head_split):
            if item and item not in items:
                items.append(item)
    return items


def parse_search_items(query: str, db_default: str = "") -> tuple[list[str], str]:
    """Agent stage 1: turn a free-form query into a list of items.

    Returns (items, method) where method is 'llm' or 'fallback'.
    Always returns at least one item for non-empty queries.
    """
    query = (query or "").strip()
    if not query:
        return [], "fallback"

    items: list[str] = []
    method = "fallback"

    # Thinking models (e.g. gemini-2.5-flash) burn output tokens on reasoning,
    # so give generous headroom and retry with more if the JSON came back truncated.
    raw = ai.call_text(_PARSE_PROMPT.format(query=query), db_default, max_tokens=1024)
    if raw and raw.rfind("]") <= raw.find("["):
        raw = ai.call_text(_PARSE_PROMPT.format(query=query), db_default, max_tokens=2048)
    if raw:
        # Tolerate markdown fences / prose around the JSON array.
        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(raw[start:end + 1])
                if isinstance(parsed, list):
                    items = [str(x).strip().lower() for x in parsed if str(x).strip()]
                    if items:
                        method = "llm"
            except (ValueError, TypeError):
                items = []

    if not items:
        items = _fallback_parse(query)

    if not items:
        items = [query.lower()]

    # De-duplicate while preserving order, cap at 8 items to keep the pipeline snappy.
    seen: set[str] = set()
    unique = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:8], method
