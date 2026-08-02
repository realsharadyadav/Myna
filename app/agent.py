"""Agentic search pipeline.

Stage 1 — Query understanding: split a free-form query ("salt milk and mango",
"kala namak, doodh 1L") into individual shopping items. Uses the configured
LLM provider (fast, handles Hinglish/synonyms); falls back to a rule-based
split on commas / 'and' / '&' / '+' when no provider is configured or the
LLM call fails — so search keeps working without any API key.

Stage 1.5 — Concept expansion (expand_concept): for vague "concept" queries
("pooja items", "chicken biryani ingredients") rather than plain item lists,
grounds the LLM with a web search (app/web_search.py) before it expands the
concept into concrete items — catches ingredients/items the model's own
knowledge would otherwise silently miss. Purely additive: an empty/failed
search just leaves the LLM to its own knowledge, same as before.

Stage 2 (in routers/search.py) — Retrieval: run the existing fuzzy matcher
for every parsed item.

Stage 3 (in routers/search.py) — Aggregation: group hits per shop, compute
how many of the requested items each shop covers, and rank shops by
coverage (most items found first), then distance (nearest first).
"""

import json
import re

from . import ai, dishes, web_search

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

_EXPAND_PROMPT = """You expand a shopping *concept* into the concrete grocery/pooja items
it implies, so a hyperlocal search engine can match them against shop catalogues.

Examples:
- "pooja items" -> ["agarbatti","camphor","haldi","kumkum","diya","coconut","flowers","rakhi"]
- "breakfast" -> ["bread","eggs","milk","butter","jam"]
- "baby care" -> ["diapers","baby food","wipes","powder"]

Rules:
- 6–12 specific, commonly-stocked items
- Include common Hindi/Hinglish names alongside English where natural
  ("agarbatti" not just "incense", "haldi" not just "turmeric")
- Single words or short multi-word products
- Web search results are attached below for grounding — use them to catch
  items you might otherwise miss (e.g. a less common dish's full ingredient
  list), but only pull out actual purchasable grocery/shop items. Ignore
  recipe steps, quantities, ads, or anything not a concrete item.
- Reply with ONLY a JSON array of lowercase strings.

Web search results:
{web_context}

Concept: "{query}\""""

# Regex that detects "concept" phrasing the user might type instead of items:
# "looking for pooja items", "things for puja", "stuff for a party" etc.
_CONCEPT_HINTS_RE = re.compile(
    r"\b(items?|things?|stuff|for|saman|samaan|ka\s+saman)\b", re.IGNORECASE
)


_DISH_PROMPT = """You are the ingredient planner of a hyperlocal grocery search engine.
The user named a dish they want to cook. List the grocery items they need to BUY for it.

Rules:
- 6–12 concrete, commonly-stocked shop items
- Use the names Indian kirana shopkeepers use, Hinglish where natural
  ("haldi" not "turmeric powder", "paneer", "toor dal", "garam masala")
- Ingredients only — no quantities, no steps, no utensils, no "water"/"salt to taste"
- Web search results are attached for grounding; use them to catch ingredients
  you would otherwise miss, and ignore recipe steps, ads and anything that
  isn't a purchasable item.
- Reply with ONLY a JSON array of lowercase strings.

Web search results:
{web_context}

Dish: "{query}\""""


def _json_array(raw: str) -> list[str]:
    """Pull a JSON array of strings out of an LLM reply, tolerating fences/prose."""
    if not raw:
        return []
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x).strip().lower() for x in parsed if str(x).strip()]


def expand_dish(query: str, db_default: str = "") -> tuple[list[str], str]:
    """Dish mode — turn a dish name into the shopping list it needs.

    Returns (items, method) where method is:
      'dish-llm-web' -> LLM planned the ingredients, grounded with web search
      'dish-llm'     -> LLM planned the ingredients (web search returned nothing)
      'dish-curated' -> no LLM (or it failed); curated glossary in app/dishes.py
      ''             -> unknown dish and no LLM; caller falls back to plain parse

    The curated glossary is also merged into LLM output, so a known dish never
    loses an ingredient the model happened to skip.
    """
    query = (query or "").strip()
    if not query:
        return [], ""

    curated = dishes.lookup(query)

    if ai.get_effective_default(db_default):
        dish = dishes.normalise(query) or query
        web_context = web_search.ingredient_context(f"{dish} recipe ingredients")
        prompt = _DISH_PROMPT.format(query=dish, web_context=web_context or "(no web results)")
        items = _json_array(ai.call_text(prompt, db_default, max_tokens=1024))
        if items:
            return _dedupe(items + curated)[:12], "dish-llm-web" if web_context else "dish-llm"

    if curated:
        return _dedupe(curated)[:12], "dish-curated"
    return [], ""


def expand_concept(query: str, db_default: str = "") -> tuple[list[str], str]:
    """Stage 1.5 — expand a concept query ("pooja items") into concrete items.

    Returns (items, method) where method is:
      'concept-llm-web' -> concept expanded by LLM, grounded with web search
      'concept-llm'      -> concept expanded by LLM (web search returned nothing)
      'llm'              -> LLM parsed, no expansion needed / happened
      'fallback'         -> no LLM available; rule-based split
    If the query already looks like a plain item list it is NOT expanded and the
    regular parse is used instead.
    """
    query = (query or "").strip()
    if not query:
        return [], "fallback"

    # Only attempt expansion for short "concept-ish" queries (not long item lists),
    # and only when there's an LLM configured to make use of it — otherwise this
    # call is discarded below anyway, so skip the network round-trip entirely.
    looks_concepty = bool(_CONCEPT_HINTS_RE.search(query)) or len(query.split()) <= 3
    has_list_marker = bool(re.search(r"[,+]|/|\band\b", query, re.IGNORECASE))
    if looks_concepty and not has_list_marker and ai.get_effective_default(db_default):
        # Web search catches items the model's own knowledge might miss (an
        # unusual dish's full ingredient list, a regional item name, etc).
        # Optional grounding only — an empty string here just means the LLM
        # falls back to its own knowledge, same as before this existed.
        web_context = web_search.ingredient_context(query)
        prompt = _EXPAND_PROMPT.format(query=query, web_context=web_context or "(no web results)")
        raw = ai.call_text(prompt, db_default, max_tokens=1024)
        if raw:
            start, end = raw.find("["), raw.rfind("]")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(raw[start:end + 1])
                    items = [str(x).strip().lower() for x in parsed if str(x).strip()]
                    if items:
                        return _dedupe(items), "concept-llm-web" if web_context else "concept-llm"
                except (ValueError, TypeError):
                    pass
    return [], ""  # signal: not a concept (or expansion failed) -> plain parse


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


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
    # A multi-part query is clearly a shopping list. So is a single part of 3+
    # words with no connector at all ("milk bread eggs") — that's how people
    # actually type lists on a phone, and without splitting it the whole query
    # is matched as one item and finds nothing.
    allow_head_split = len(parts) > 1 or (
        len(parts) == 1 and len(_clean_item(parts[0]).split()) > 2
    )
    for part in parts:
        for item in _split_phrase(part, allow_head_split):
            if item and item not in items:
                items.append(item)
    return items


def parse_search_items(query: str, db_default: str = "", mode: str = "") -> tuple[list[str], str]:
    """Agent stage 1 (+1.5): turn a free-form query into a list of items.

    `mode="dish"` means the user is in the app's dish mode and typed a dish
    name, so the query is expanded into the ingredients it needs before
    anything else. Otherwise: concept expansion first ("pooja items" ->
    agarbatti, camphor...) when the query looks conceptual, else a regular item
    list parse ("salt milk and mango"). Falls back to rule-based splitting
    with no LLM.

    Returns (items, method) where method is
    'dish-llm-web' | 'dish-llm' | 'dish-curated' | 'concept-llm' | 'llm' | 'fallback'.
    Always returns at least one item for non-empty queries.
    """
    query = (query or "").strip()
    if not query:
        return [], "fallback"

    # Dish mode: "paneer butter masala" -> paneer, tomato, butter, cream...
    if mode == "dish":
        cooked, dish_method = expand_dish(query, db_default)
        if cooked:
            return cooked, dish_method

    # Stage 1.5: concept expansion ("pooja items" -> concrete shopping items).
    expanded, concept_method = expand_concept(query, db_default)
    if expanded:
        return expanded, concept_method

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

    # De-duplicate while preserving order; 12 items cap (expanded concepts are longer).
    return _dedupe(items)[:12], method
