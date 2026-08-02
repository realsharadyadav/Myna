"""Curated aliases for common hyperlocal grocery terms that name the same
item but are too dissimilar as strings for substring matching, and too
dissimilar (or too short/ambiguous) for embedding similarity to reliably
tell apart from unrelated words — Hindi/Marathi names vs their English
names, and common transliteration variants (daal/dal, kapoor/camphor).

Deliberately a short, hand-picked list rather than a generic fuzzy-match
algorithm: benchmarking showed neither a lowered embedding threshold nor a
generic string-similarity ratio separates true variants (daal/dal) from
coincidentally-similar unrelated words (salt/malt, rice/dice, milk/silk) at
this word length — any single threshold either misses the variants or
lets the false positives in. A known-correct glossary has no such
false-positive risk, at the cost of only covering what's listed here.
"""

_GROUPS: list[set[str]] = [
    {"daal", "dal", "dhal"},
    {"kapoor", "kapur", "camphor"},
    {"atta", "aata", "wheat flour"},
    {"besan", "gram flour", "chickpea flour"},
    {"dhaniya", "daniya", "coriander", "cilantro"},
    {"haldi", "turmeric"},
    {"mirchi", "mirch", "chilli", "chili"},
    {"jeera", "zeera", "cumin"},
    {"chawal", "chaval", "rice"},
    {"doodh", "milk"},
    {"tel", "oil"},
    {"cheeni", "chini", "sugar"},
    {"namak", "salt"},
    {"sabun", "soap"},
]

_LOOKUP: dict[str, set[str]] = {}
for _group in _GROUPS:
    for _term in _group:
        _LOOKUP[_term] = _group


def expand(term: str) -> set[str]:
    """All known aliases for a term, including itself. Just {term} if it
    isn't in the glossary."""
    key = term.strip().lower()
    return _LOOKUP.get(key, set()) | {key}
