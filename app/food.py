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
        # Free to mean just a cart again: the app's umbrella word is "jagah",
        # so "thela" isn't doing double duty as both the general term and one
        # specific kind.
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
        "label": "Aur koi jagah",
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
#
# One rule about the names: a bucket must never be named after a specific dish.
# "Chai & drinks" meant every juice stall matched a search for "chai", because
# search reads the category too — the bucket claimed a dish it didn't sell.

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
    "Fast food": [
        "roll", "kathi roll", "egg roll", "frankie", "shawarma", "burger",
        "sandwich", "pizza", "hot dog", "maggi", "fries", "french fries", "pasta",
        "omelette", "anda", "bhurji", "toast",
    ],
    "Main course": [
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
    "Drinks": [
        "chai", "tea", "coffee", "lassi", "juice", "shikanji", "nimbu pani",
        "cold drink", "shake", "milkshake", "coconut water", "nariyal pani",
        "ganne ka ras", "sugarcane", "buttermilk", "chaas", "thandai", "soda",
    ],
    "Bakery": [
        "cake", "pastry", "patties", "puff", "bread", "bun", "biscuit", "cookie",
        "rusk", "khari", "muffin", "donut",
    ],
}

DEFAULT_CATEGORY = "Fast food"

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


# ---------------------------------------------------------------------------
# Query terms
# ---------------------------------------------------------------------------

# Words that join a list rather than name a dish. "momos aur chowmein" is two
# things wanted, not three.
JOINERS = {"aur", "and", "or", "ya", "plus", "with", "ke", "ka", "ki", "wala",
           "wale", "chahiye", "chaiye", "milega", "milta", "hai", "near", "me",
           "mein", "kuch", "koi"}


def split_query(text: str) -> list[str]:
    """"momos aur chawmin" -> ["momos", "chawmin"].

    Multi-word dishes survive: a phrase that matches the vocabulary as a whole
    ("chole bhature", "pav bhaji") is kept together rather than split into two
    words that each mean something else on their own.
    """
    cleaned = (text or "").lower().replace(",", " ").replace("+", " ")
    words = [w for w in cleaned.split() if w and w not in JOINERS]
    if not words:
        return []

    known = vocabulary()
    terms: list[str] = []
    i = 0
    while i < len(words):
        pair = f"{words[i]} {words[i + 1]}" if i + 1 < len(words) else ""
        if pair and pair in known:
            terms.append(pair)
            i += 2
        else:
            terms.append(words[i])
            i += 1
    # Preserve order but drop repeats — "chai chai" is one thing wanted.
    seen: set[str] = set()
    return [t for t in terms if len(t) > 1 and not (t in seen or seen.add(t))]


# ---------------------------------------------------------------------------
# Synonyms
# ---------------------------------------------------------------------------
# The same food goes by different names in different mouths — regionally
# ("golgappe" in Delhi, "puchka" in Kolkata, "gupchup" in Odisha), across
# languages ("anda"/"egg", "machli"/"fish"), and between what a customer types
# and what a board writes ("dumpling" vs "Momos").
#
# Spelling correction can't help here: these words aren't misspellings of each
# other, they share no letters. Embeddings can, but they need a model that has
# to download first and may not be available at all. A curated list needs
# neither, is instant, and — for a vocabulary this small and this well known —
# is more reliable than either. Each line is one food; every word on it matches
# every other.

SYNONYM_GROUPS: list[list[str]] = [
    ["momos", "momo", "dimsum", "dumpling", "dumplings", "momoz"],
    ["chowmein", "chow mein", "noodles", "chaumin", "hakka noodles"],
    ["golgappe", "golgappa", "pani puri", "panipuri", "puchka", "phuchka",
     "gupchup", "batasha", "paani puri"],
    ["samosa", "samose", "singhara"],
    ["pakora", "pakode", "bhajiya", "bhaji", "fritters"],
    ["chai", "tea"],
    ["coffee", "kaapi"],
    ["lassi", "chaach", "chaas", "buttermilk", "matha"],
    ["ganne ka ras", "sugarcane juice", "sugarcane", "ganna"],
    ["nariyal pani", "coconut water", "nariyal"],
    ["shikanji", "nimbu pani", "lemonade", "nimboo pani", "lemon soda"],
    ["anda", "egg", "omelette", "omlet", "bhurji"],
    ["roti", "chapati", "chapatti", "phulka"],
    ["paratha", "parantha", "parotha"],
    ["chole bhature", "chhole bhature", "chana bhatura", "bhature"],
    ["pav bhaji", "pao bhaji", "pavbhaji"],
    ["vada pav", "wada pav", "vadapav"],
    ["aloo tikki", "tikki", "potato patty"],
    ["biryani", "biriyani", "biryani rice"],
    ["jalebi", "jilebi", "imarti"],
    ["gulab jamun", "gulabjamun"],
    ["mithai", "sweets", "sweet", "dessert", "misthan"],
    ["ice cream", "icecream", "kulfi"],
    ["dosa", "dosai", "masala dosa"],
    ["idli", "idly"],
    ["roll", "kathi roll", "frankie", "wrap"],
    ["shawarma", "shawarama", "shwarma"],
    ["maggi", "instant noodles"],
    ["paneer", "cottage cheese"],
    ["chicken", "murgh", "murga", "non veg", "nonveg"],
    ["mutton", "gosht", "bakra"],
    ["fish", "machli", "machhli"],
    ["thali", "full meal", "meal", "khana", "khaana"],
    ["kachori", "kachauri"],
    ["burger", "bugger"],
    ["sandwich", "sandwitch"],
    ["juice", "sharbat"],
    ["halwa", "halva"],
    ["poha", "pohe"],
    ["upma", "uppuma"],
    ["rajma chawal", "rajma rice", "rajma"],
]

# word -> every word meaning the same food, built once at import.
SYNONYMS: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    for _word in _group:
        SYNONYMS.setdefault(_word, set()).update(_group)


# Matching is prefix-friendly so "momo" finds "Momos", which makes a very short
# synonym actively dangerous: "cha" for chai matched every *Chaat* stall, and
# "ras" for juice matched Rasgulla and Rasam. Four characters is the floor.
MIN_SYNONYM_LENGTH = 4


def canonical(term: str) -> str:
    """The name a food is best known by, for showing back to the user.

    Each group's first word is the canonical one, so a correction that lands on
    "chaumin" is reported as "chowmein" — the spelling someone recognises.
    """
    word = (term or "").strip().lower()
    for group in SYNONYM_GROUPS:
        if word in group:
            return group[0]
    return word


def synonyms_of(term: str) -> set[str]:
    """Every other name for the same food. Empty when the word isn't in a group."""
    group = SYNONYMS.get((term or "").strip().lower(), set())
    return {word for word in group if len(word) >= MIN_SYNONYM_LENGTH}


def vocabulary(extra: set[str] | None = None) -> set[str]:
    """Every dish word the app knows, for spelling correction to aim at.

    `extra` is for dish names actually on menus nearby — a vendor selling
    something the built-in list never heard of should still be findable when
    the customer misspells it.
    """
    words: set[str] = set()
    for hints in CATEGORIES.values():
        words.update(hints)
    for chip in POPULAR:
        words.add(chip.lower())
    for kind in KINDS.values():
        words.update(kind["hints"])
    words.update(SYNONYMS)
    if extra:
        words.update(w for w in extra if w)
    return words


# 0.72 is deliberately loose enough for the transliteration spread these names
# get — "chawmin"/"chow mein"/"chowmin" are all the same food — and tight
# enough that "chai" doesn't quietly become "chaat".
_FUZZY_CUTOFF = 0.72


def correct_term(term: str, known: set[str] | None = None) -> str:
    """Fix an obvious misspelling against the dish vocabulary.

    Returns the term unchanged when it's already known or nothing is close —
    guessing wrong is worse than not guessing, because a wrong correction
    silently searches for a different food.
    """
    from difflib import get_close_matches

    word = (term or "").strip().lower()
    if not word:
        return term
    words = known if known is not None else vocabulary()
    if word in words:
        return word
    # A known dish containing the term ("momo" inside "momos") is a prefix
    # match, not a misspelling — leave it for substring matching to handle.
    if any(word in candidate for candidate in words):
        return word
    hit = get_close_matches(word, words, n=1, cutoff=_FUZZY_CUTOFF)
    return hit[0] if hit else word


# Chips on the home screen — what people actually walk out to buy.
POPULAR = [
    "Momos", "Chowmein", "Golgappe", "Chai", "Samosa", "Maggi", "Roll",
    "Chole bhature", "Dosa", "Paratha", "Jalebi", "Vada pav", "Biryani",
    "Pav bhaji", "Lassi", "Ice cream",
]
