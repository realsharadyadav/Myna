"""Curated dish → ingredient shopping lists.

Powers the "search by dish name" mode: the customer types a dish
("paneer butter masala", "poha") and Myna turns it into the shopping list of
things they need to buy, then finds nearby shops that stock them.

The LLM (app/agent.py, grounded with web search) handles the long tail. This
module is the zero-config path: without any API key the dish mode still works
for the dishes people actually search for, and it also normalises the noisy
ways users type a dish ("poha recipe", "how to make maggi", "biryani banane
ka saman").

Ingredient names deliberately mix English and Hinglish ("haldi", "paneer") —
downstream matching expands those through app/synonyms.py and embeddings, so
listing the word shopkeepers actually use gives the best hit rate.
"""

import re

# Words users tack onto a dish name that aren't part of the dish itself.
_NOISE_RE = re.compile(
    r"\b(recipe|recipes|ingredients?|saman|samaan|saamaan|banane|banana|banao|"
    r"banaye|banane\s+ka|kaise|how|to|make|making|cook|cooking|for|ke\s+liye|"
    r"ka|ki|ke|need|needed|list|shopping|buy)\b",
    re.IGNORECASE,
)

_DISHES: dict[str, list[str]] = {
    "poha": ["poha", "onion", "green chilli", "mustard seeds", "haldi", "peanuts", "curry leaves", "lemon"],
    "upma": ["rava", "onion", "green chilli", "mustard seeds", "curry leaves", "urad dal", "oil"],
    "maggi": ["maggi", "onion", "tomato", "green chilli", "butter"],
    "chai": ["tea leaves", "doodh", "cheeni", "adrak", "elaichi"],
    "paneer butter masala": ["paneer", "tomato", "onion", "butter", "cream", "cashew", "ginger garlic paste", "garam masala", "kasuri methi"],
    "shahi paneer": ["paneer", "onion", "tomato", "cashew", "cream", "garam masala", "butter"],
    "palak paneer": ["paneer", "palak", "onion", "tomato", "ginger garlic paste", "jeera", "garam masala"],
    "chole": ["kabuli chana", "onion", "tomato", "chole masala", "ginger garlic paste", "tea leaves", "oil"],
    "rajma": ["rajma", "onion", "tomato", "ginger garlic paste", "garam masala", "jeera", "haldi"],
    "dal tadka": ["toor dal", "onion", "tomato", "haldi", "jeera", "ghee", "hing", "dhaniya"],
    "dal makhani": ["urad dal", "rajma", "butter", "cream", "tomato", "ginger garlic paste", "garam masala"],
    "khichdi": ["chawal", "moong dal", "haldi", "jeera", "ghee", "hing"],
    "biryani": ["basmati chawal", "chicken", "curd", "onion", "biryani masala", "mint", "dhaniya", "ghee", "saffron"],
    "veg biryani": ["basmati chawal", "curd", "onion", "gajar", "matar", "biryani masala", "mint", "ghee"],
    "pulao": ["basmati chawal", "onion", "matar", "gajar", "jeera", "garam masala", "ghee"],
    "butter chicken": ["chicken", "butter", "tomato", "cream", "curd", "ginger garlic paste", "garam masala", "kasuri methi"],
    "chicken curry": ["chicken", "onion", "tomato", "ginger garlic paste", "haldi", "mirchi", "garam masala", "dhaniya"],
    "egg curry": ["eggs", "onion", "tomato", "ginger garlic paste", "haldi", "garam masala", "dhaniya"],
    "pav bhaji": ["pav", "aloo", "matar", "gobi", "tomato", "onion", "capsicum", "pav bhaji masala", "butter"],
    "vada pav": ["pav", "aloo", "besan", "green chilli", "mustard seeds", "haldi", "curry leaves", "oil"],
    "misal pav": ["matki", "pav", "onion", "misal masala", "farsan", "lemon", "dhaniya"],
    "dosa": ["chawal", "urad dal", "methi dana", "namak", "oil", "aloo", "onion"],
    "idli": ["idli rava", "urad dal", "methi dana", "namak"],
    "sambar": ["toor dal", "sambar masala", "imli", "onion", "tomato", "drumstick", "mustard seeds", "curry leaves"],
    "rasam": ["toor dal", "imli", "tomato", "rasam powder", "jeera", "curry leaves", "hing"],
    "chole bhature": ["kabuli chana", "maida", "curd", "chole masala", "onion", "oil", "baking soda"],
    "rajma chawal": ["rajma", "chawal", "onion", "tomato", "ginger garlic paste", "garam masala"],
    "aloo paratha": ["atta", "aloo", "green chilli", "dhaniya", "garam masala", "ghee", "curd"],
    "paratha": ["atta", "ghee", "namak", "curd"],
    "roti": ["atta", "namak", "ghee"],
    "puri": ["atta", "sooji", "oil", "namak"],
    "samosa": ["maida", "aloo", "matar", "jeera", "garam masala", "green chilli", "oil"],
    "pakora": ["besan", "onion", "aloo", "green chilli", "ajwain", "mirchi", "oil"],
    "kadhi": ["besan", "curd", "haldi", "methi dana", "mirchi", "hing", "curry leaves"],
    "matar paneer": ["paneer", "matar", "onion", "tomato", "ginger garlic paste", "garam masala"],
    "aloo gobi": ["aloo", "gobi", "haldi", "jeera", "dhaniya", "mirchi", "oil"],
    "baingan bharta": ["baingan", "onion", "tomato", "green chilli", "ginger garlic paste", "dhaniya"],
    "bhindi masala": ["bhindi", "onion", "tomato", "amchur", "haldi", "dhaniya", "oil"],
    "halwa": ["sooji", "cheeni", "ghee", "elaichi", "kaju", "kishmish"],
    "kheer": ["chawal", "doodh", "cheeni", "elaichi", "kaju", "kishmish"],
    "gulab jamun": ["milk powder", "maida", "cheeni", "ghee", "elaichi"],
    "besan ladoo": ["besan", "ghee", "cheeni", "elaichi", "kaju"],
    "fried rice": ["chawal", "capsicum", "gajar", "beans", "soy sauce", "spring onion", "oil"],
    "pasta": ["pasta", "tomato", "cheese", "capsicum", "olive oil", "oregano", "garlic"],
    "maggi masala": ["maggi", "onion", "tomato", "butter", "green chilli"],
    "sandwich": ["bread", "butter", "tomato", "onion", "cucumber", "cheese", "chutney"],
    "omelette": ["eggs", "onion", "green chilli", "tomato", "dhaniya", "oil"],
    "pongal": ["chawal", "moong dal", "ghee", "kali mirch", "jeera", "adrak", "kaju"],
    "thepla": ["atta", "methi", "besan", "haldi", "curd", "oil"],
    "dhokla": ["besan", "curd", "eno", "green chilli", "mustard seeds", "curry leaves", "cheeni"],
}

# Alternate spellings / short forms people type, mapped to a canonical key.
_ALIASES: dict[str, str] = {
    "pbm": "paneer butter masala",
    "paneer makhani": "paneer butter masala",
    "murgh makhani": "butter chicken",
    "chana masala": "chole",
    "chhole": "chole",
    "chicken biryani": "biryani",
    "hyderabadi biryani": "biryani",
    "masala dosa": "dosa",
    "sada dosa": "dosa",
    "poha recipe": "poha",
    "aalu paratha": "aloo paratha",
    "alu paratha": "aloo paratha",
    "sooji halwa": "halwa",
    "suji halwa": "halwa",
    "rava upma": "upma",
    "veg pulao": "pulao",
    "matar pulao": "pulao",
    "anda curry": "egg curry",
    "bhindi": "bhindi masala",
    "kadai paneer": "matar paneer",
}


def normalise(query: str) -> str:
    """Strip recipe-speak so 'how to make poha recipe' → 'poha'."""
    text = _NOISE_RE.sub(" ", query or "")
    text = re.sub(r"[^a-zA-Zऀ-ॿ\s\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def lookup(query: str) -> list[str]:
    """Curated ingredient list for a dish, or [] if it isn't in the glossary.

    Matches the normalised query exactly, then by alias, then by the longest
    known dish name contained in the query ("aaj palak paneer banana hai").
    """
    key = normalise(query)
    if not key:
        return []
    if key in _DISHES:
        return list(_DISHES[key])
    if key in _ALIASES:
        return list(_DISHES[_ALIASES[key]])
    for name in sorted(_DISHES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", key):
            return list(_DISHES[name])
    for alias in sorted(_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", key):
            return list(_DISHES[_ALIASES[alias]])
    return []


def popular(limit: int = 12) -> list[str]:
    """A few well-known dishes, for the app's suggestion chips."""
    picks = [
        "poha", "maggi", "paneer butter masala", "biryani", "chole",
        "pav bhaji", "dal tadka", "aloo paratha", "dosa", "rajma",
        "butter chicken", "kheer",
    ]
    return picks[:limit]
