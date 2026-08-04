"""Food-only vocabulary: what kinds of vendors exist, and what they sell.

Myna is now about *khaana* — the thela, tapri, chaat corner and dhaba that no
delivery app has ever listed. This module is the shared vocabulary for that:
the kinds of vendor a photo can turn out to be, the food categories items get
sorted into, and the Hinglish words the UI puts on screen.

Everything here is deliberately Hinglish-in-Roman rather than English or
Devanagari: it's how the food is actually named out loud ("chowmein", "chole
bhature"), it needs no font support on a cheap phone, and it's what someone
types into the search box.
"""

# ---------------------------------------------------------------------------
# Vendor kinds
# ---------------------------------------------------------------------------
# `label` is what a card shows, `hints` are the words in a signboard (or a
# search query) that point at this kind, and `mobile` says whether this kind is
# normally a moving thela — which decides if the add flow asks for timings.

KINDS: dict[str, dict] = {
    "thela": {
        "label": "Thela",
        "emoji": "🛒",
        "mobile": True,
        "hints": ["thela", "cart", "rehri", "pheri", "khomcha"],
    },
    "chaat": {
        "label": "Chaat corner",
        "emoji": "🥘",
        "mobile": False,
        # Hinglish plurals are how people actually write these — "golgappe" is
        # far commoner than "golgappa", and it's the spelling on our own chips.
        "hints": ["chaat", "golgappa", "golgappe", "gol gappe", "panipuri",
                  "pani puri", "papdi", "tikki", "bhelpuri", "bhel", "dahi puri",
                  "sev puri", "raj kachori", "samosa", "samose", "pakora", "pakode"],
    },
    "chinese": {
        "label": "Chinese thela",
        "emoji": "🍜",
        "mobile": False,
        "hints": ["chowmein", "chow mein", "noodles", "momo", "momos", "manchurian",
                  "spring roll", "fried rice", "hakka", "chinese"],
    },
    "chai": {
        "label": "Chai tapri",
        "emoji": "☕",
        "mobile": False,
        "hints": ["chai", "tea", "tapri", "kulhad", "coffee", "bun maska", "rusk"],
    },
    "dhaba": {
        "label": "Dhaba",
        "emoji": "🍛",
        "mobile": False,
        "hints": ["dhaba", "bhojanalya", "bhojnalaya", "thali", "punjabi", "tandoor",
                  "roti", "dal fry", "paratha"],
    },
    "sweets": {
        "label": "Mithai shop",
        "emoji": "🍬",
        "mobile": False,
        "hints": ["mithai", "sweet", "sweets", "halwai", "jalebi", "laddu", "barfi",
                  "rasgulla", "gulab jamun", "imarti"],
    },
    "juice": {
        "label": "Juice / shikanji",
        "emoji": "🥤",
        "mobile": False,
        "hints": ["juice", "shikanji", "nimbu pani", "lassi", "shake", "coconut water",
                  "nariyal pani", "ganne ka ras", "sugarcane", "falooda"],
    },
    "bakery": {
        "label": "Bakery",
        "emoji": "🥖",
        "mobile": False,
        "hints": ["bakery", "cake", "pastry", "patties", "bread", "puff", "biscuit"],
    },
    "tiffin": {
        "label": "Tiffin / mess",
        "emoji": "🍱",
        "mobile": False,
        "hints": ["tiffin", "mess", "bhojan", "home food", "ghar ka khana", "dabba"],
    },
    "restaurant": {
        "label": "Restaurant",
        "emoji": "🍽️",
        "mobile": False,
        "hints": ["restaurant", "cafe", "family", "hotel", "diner", "kitchen"],
    },
    "other": {
        "label": "Khaane ki dukaan",
        "emoji": "🍴",
        "mobile": False,
        "hints": [],
    },
}

DEFAULT_KIND = "other"

# Kinds ordered for the picker: the ones a street-food app sees most, first.
KIND_ORDER = ["thela", "chinese", "chaat", "chai", "juice", "dhaba", "sweets",
              "bakery", "tiffin", "restaurant", "other"]


def normalise_kind(value: str | None) -> str:
    """Accept whatever the AI or the client sent and land on a known kind."""
    key = (value or "").strip().lower().replace(" ", "_")
    if key in KINDS:
        return key
    # A model asked for "kind" often answers with a word from the board instead
    # ("momos"), so fall back to matching that word against the hints.
    for kind in KIND_ORDER:
        if any(hint in key for hint in KINDS[kind]["hints"]):
            return kind
    return DEFAULT_KIND


def kind_label(value: str | None) -> str:
    return KINDS[normalise_kind(value)]["label"]


def kind_emoji(value: str | None) -> str:
    return KINDS[normalise_kind(value)]["emoji"]


def is_mobile_kind(value: str | None) -> bool:
    return KINDS[normalise_kind(value)]["mobile"]


def kind_list() -> list[dict]:
    """Kinds in picker order, shaped for the client."""
    return [
        {"kind": k, "label": KINDS[k]["label"], "emoji": KINDS[k]["emoji"],
         "mobile": KINDS[k]["mobile"]}
        for k in KIND_ORDER
    ]


# ---------------------------------------------------------------------------
# Food categories
# ---------------------------------------------------------------------------
# Small on purpose. A street-food menu doesn't need sixteen aisles, and a short
# list is one the vision model actually picks from instead of inventing its own.

CATEGORIES: dict[str, list[str]] = {
    "Chaat & street": [
        "golgappa", "golgappe", "gol gappe", "pani puri", "panipuri", "puchka",
        "phuchka", "bhel", "bhelpuri", "papdi",
        "tikki", "aloo tikki", "dahi puri", "sev puri", "raj kachori", "chaat",
        "kachori", "samosa", "samose", "pakora", "pakode", "bhajiya",
        "vada pav", "vada", "dabeli", "pav bhaji", "chole bhature",
        "chole", "bhature", "kulcha", "litti", "chokha", "dahi vada",
    ],
    "Chinese": [
        "chowmein", "chow mein", "noodles", "momo", "momos", "manchurian",
        "spring roll", "fried rice", "hakka", "chilli potato", "honey chilli",
        "schezwan", "soup", "dimsum",
    ],
    "Rolls & fast food": [
        "roll", "kathi roll", "egg roll", "frankie", "shawarma", "burger",
        "sandwich", "pizza", "hot dog", "maggi", "fries", "french fries", "pasta",
        "omelette", "anda", "bhurji", "toast",
    ],
    "Tandoor & main course": [
        "roti", "naan", "tandoori", "paratha", "thali", "dal", "paneer",
        "butter masala", "kadhai", "biryani", "pulao", "rajma", "chawal", "curry",
        "sabzi", "kofta", "korma", "tikka", "kebab", "chicken", "mutton", "fish",
    ],
    "South Indian": [
        "dosa", "idli", "vada sambar", "uttapam", "sambar", "rasam", "upma", "poha",
        "medu vada", "appam", "pongal",
    ],
    "Sweets": [
        "jalebi", "laddu", "ladoo", "barfi", "burfi", "rasgulla", "gulab jamun",
        "imarti", "halwa", "rabri", "kheer", "gajak", "peda", "sandesh", "mithai",
        "ice cream", "kulfi", "falooda",
    ],
    "Chai & drinks": [
        "chai", "tea", "coffee", "lassi", "juice", "shikanji", "nimbu pani",
        "cold drink", "shake", "milkshake", "coconut water", "nariyal pani",
        "ganne ka ras", "sugarcane", "buttermilk", "chaas", "thandai", "soda",
    ],
    "Bakery": [
        "cake", "pastry", "patties", "puff", "bread", "bun", "biscuit", "cookie",
        "rusk", "khari", "muffin", "donut",
    ],
}

DEFAULT_CATEGORY = "Rolls & fast food"

CATEGORY_NAMES = list(CATEGORIES.keys())


def suggest_category(name: str) -> str:
    """Best-guess food category for a dish name.

    Longest hint wins, so "chilli potato" doesn't get claimed by a shorter
    match somewhere else in the table.
    """
    text = (name or "").strip().lower()
    if not text:
        return DEFAULT_CATEGORY
    best_category, best_len = "", 0
    for category, hints in CATEGORIES.items():
        for hint in hints:
            if hint in text and len(hint) > best_len:
                best_category, best_len = category, len(hint)
    return best_category or DEFAULT_CATEGORY


def normalise_category(value: str | None, name: str = "") -> str:
    """Keep a known category, otherwise re-derive one from the dish name."""
    candidate = (value or "").strip()
    for known in CATEGORY_NAMES:
        if candidate.lower() == known.lower():
            return known
    return suggest_category(name or candidate)


# ---------------------------------------------------------------------------
# "Nahi mila" — why?
# ---------------------------------------------------------------------------
# A cart being absent means three completely different things, and treating
# them alike is what kills good listings: a chaat wala shut for one Tuesday
# would otherwise be voted down by exactly the people it serves best.
#
# `weight` is how much a report argues the listing is *wrong*:
#   0  — the listing is right, the vendor just isn't there today
#   1  — this spot looks wrong (moved on, or nobody knows why)
#   3  — the vendor is gone for good, so a couple of these retire the listing

SEEN_REASONS: dict[str, dict] = {
    "closed_today": {
        "label": "Aaj band hai",
        "hint": "Chhutti ya aaj nahi aaya",
        "weight": 0,
    },
    "moved": {
        "label": "Yahan se hat gaya",
        "hint": "Ab kisi aur jagah lagta hai",
        "weight": 1,
    },
    "shut_down": {
        "label": "Hamesha ke liye band",
        "hint": "Ab lagta hi nahi",
        "weight": 3,
    },
    "unknown": {
        "label": "Pata nahi, bas nahi mila",
        "hint": "",
        "weight": 1,
    },
}

DEFAULT_SEEN_REASON = "unknown"


def normalise_seen_reason(value: str | None) -> str:
    key = (value or "").strip().lower().replace(" ", "_")
    return key if key in SEEN_REASONS else DEFAULT_SEEN_REASON


def seen_reason_list() -> list[dict]:
    """Reasons in the order the sheet offers them — least damaging first, so
    the easy honest answer ("aaj band hai") is the one under the thumb."""
    return [
        {"reason": r, "label": SEEN_REASONS[r]["label"], "hint": SEEN_REASONS[r]["hint"]}
        for r in ("closed_today", "moved", "shut_down", "unknown")
    ]


# ---------------------------------------------------------------------------
# Reports — "ye listing hi galat hai"
# ---------------------------------------------------------------------------
# Separate from the seen votes on purpose. A vote is about *today*; a report is
# about the listing existing at all, and only reports can hide one.

REPORT_REASONS: dict[str, str] = {
    "fake": "Aisi koi dukaan hai hi nahi",
    "joke": "Mazaak / bakwaas entry",
    "wrong": "Jankari galat hai",
    "duplicate": "Ye pehle se listed hai",
    "offensive": "Galat ya offensive content",
}

DEFAULT_REPORT_REASON = "wrong"

# How many distinct people it takes to pull a listing out of search. Low enough
# that obvious junk goes fast, high enough that one annoyed person can't
# delete a competitor. Hiding is reversible and never deletes anything — the
# owner panel reviews and restores.
REPORTS_TO_HIDE = 3


def normalise_report_reason(value: str | None) -> str:
    key = (value or "").strip().lower()
    return key if key in REPORT_REASONS else DEFAULT_REPORT_REASON


def report_reason_list() -> list[dict]:
    return [{"reason": r, "label": label} for r, label in REPORT_REASONS.items()]


# Chips on the home screen — what people actually walk out to buy.
POPULAR = [
    "Momos", "Chowmein", "Golgappe", "Chai", "Samosa", "Maggi", "Roll",
    "Chole bhature", "Dosa", "Paratha", "Jalebi", "Vada pav", "Biryani",
    "Pav bhaji", "Lassi", "Ice cream",
]
