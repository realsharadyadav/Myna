"""Shared vocabulary: what kinds of vendors exist, and what they sell or do.

Myna answers "where do I get this near me" — and that question is not only
about food. Street food was the whole app for a while and is now one family
among several, because the expensive version of the question is the one a
village has no answer to at all: which of a hundred shops stocks a water
tanki, and who can still repair a watch.

Everything here is deliberately Hinglish-in-Roman rather than English or
Devanagari: it's how these things are actually named out loud ("chowmein",
"tanki", "silai"), it needs no font support on a cheap phone, and it's what
someone types into the search box.

(This module is still named food.py; renaming it, `/api/food/*` and
`Shop.food_kind` is a mechanical pass deliberately left for later, so that
widening the domain and moving every reference don't land in one diff.)
"""

# ---------------------------------------------------------------------------
# Vendor families
# ---------------------------------------------------------------------------
# The distinction that matters is not food-vs-rest, it's **perishable presence
# vs durable fact**.
#
# A chai tapri either is at the corner right now or it isn't, so its listing is
# only worth as much as its last sighting, and "is it open" outranks everything
# else. A hardware shop stocking water tanks is a fact that stays true for
# months, and sinking it at 8 PM because the shutter is down would be the wrong
# answer to "who has one". Same for a capability: whoever repairs watches this
# year will still repair them next year.
#
# So `perishable` — not the family name — is what ranking and freshness read.

FAMILIES: dict[str, dict] = {
    "food": {
        "label": "Khaana",
        "emoji": "🍽️",
        # Presence expires: confirm it or stop trusting it.
        "perishable": True,
    },
    "goods": {
        "label": "Saamaan",
        "emoji": "🛍️",
        "perishable": False,
    },
    "services": {
        "label": "Kaam / repair",
        "emoji": "🔧",
        "perishable": False,
    },
}

DEFAULT_FAMILY = "goods"


# ---------------------------------------------------------------------------
# Vendor kinds
# ---------------------------------------------------------------------------
# `label` is what a card shows, `hints` are the words in a signboard (or a
# search query) that point at this kind, `mobile` says whether this kind is
# normally a moving thela — which decides if the add flow asks for timings —
# and `family` decides how the listing is ranked and kept fresh.
#
# `mobile` and `family` are independent: a sabzi thela is goods *and* moves.

KINDS: dict[str, dict] = {
    "thela": {
        # Free to mean just a cart again: the app's umbrella word is "jagah",
        # so "thela" isn't doing double duty as both the general term and one
        # specific kind.
        "label": "Thela",
        "emoji": "🛒",
        "family": "food",
        "mobile": True,
        "hints": ["thela", "cart", "rehri", "pheri", "khomcha"],
    },
    "chaat": {
        "label": "Chaat corner",
        "emoji": "🥘",
        "family": "food",
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
        "family": "food",
        "mobile": False,
        "hints": ["chowmein", "chow mein", "noodles", "momo", "momos", "manchurian",
                  "spring roll", "fried rice", "hakka", "chinese"],
    },
    "chai": {
        "label": "Chai tapri",
        "emoji": "☕",
        "family": "food",
        "mobile": False,
        "hints": ["chai", "tea", "tapri", "kulhad", "coffee", "bun maska", "rusk"],
    },
    "dhaba": {
        "label": "Dhaba",
        "emoji": "🍛",
        "family": "food",
        "mobile": False,
        "hints": ["dhaba", "bhojanalya", "bhojnalaya", "thali", "punjabi", "tandoor",
                  "roti", "dal fry", "paratha"],
    },
    "sweets": {
        "label": "Mithai shop",
        "emoji": "🍬",
        "family": "food",
        "mobile": False,
        "hints": ["mithai", "sweet", "sweets", "halwai", "jalebi", "laddu", "barfi",
                  "rasgulla", "gulab jamun", "imarti"],
    },
    "juice": {
        "label": "Juice / shikanji",
        "emoji": "🥤",
        "family": "food",
        "mobile": False,
        "hints": ["juice", "shikanji", "nimbu pani", "lassi", "shake", "coconut water",
                  "nariyal pani", "ganne ka ras", "sugarcane", "falooda"],
    },
    "bakery": {
        "label": "Bakery",
        "emoji": "🥖",
        "family": "food",
        "mobile": False,
        "hints": ["bakery", "cake", "pastry", "patties", "bread", "puff", "biscuit"],
    },
    "tiffin": {
        "label": "Tiffin / mess",
        "emoji": "🍱",
        "family": "food",
        "mobile": False,
        "hints": ["tiffin", "mess", "bhojan", "home food", "ghar ka khana", "dabba"],
    },
    "restaurant": {
        "label": "Restaurant",
        "emoji": "🍽️",
        "family": "food",
        "mobile": False,
        "hints": ["restaurant", "cafe", "family", "hotel", "diner", "kitchen"],
    },
    "other": {
        # The food family's catch-all, and still the default for a listing
        # whose kind nothing could work out. Everything that existed before the
        # app widened carries this, so it stays in `food` — flipping it would
        # silently change how every one of those listings ranks.
        "label": "Aur koi jagah",
        "emoji": "🍴",
        "family": "food",
        "mobile": False,
        "hints": [],
    },

    # --- Saamaan: shops that sell things ---------------------------------
    "kirana": {
        "label": "Kirana / general store",
        "emoji": "🏪",
        "family": "goods",
        "mobile": False,
        "hints": ["kirana", "karyana", "general store", "provision", "grocery",
                  "atta", "chawal", "namak", "sabun", "daily needs"],
    },
    "hardware": {
        "label": "Hardware",
        "emoji": "🔩",
        "family": "goods",
        "mobile": False,
        "hints": ["hardware", "sanitary", "cement", "tanki", "water tank", "pipe",
                  "sariya", "paint", "plywood", "tiles", "loha", "nal"],
    },
    "electrical": {
        "label": "Electrical",
        "emoji": "💡",
        "family": "goods",
        "mobile": False,
        "hints": ["electrical", "bijli", "wire", "bulb", "switch", "inverter",
                  "solar", "motor", "pankha", "holder"],
    },
    "electronics": {
        "label": "Mobile / electronics",
        "emoji": "📱",
        "family": "goods",
        "mobile": False,
        "hints": ["electronics", "mobile", "phone", "charger", "modem", "router",
                  "laptop", "computer", "earphone", "speaker", "tv"],
    },
    "medical": {
        "label": "Medical",
        "emoji": "💊",
        "family": "goods",
        "mobile": False,
        "hints": ["medical", "chemist", "pharmacy", "dawa", "dawai", "medicine",
                  "clinic"],
    },
    "stationery": {
        "label": "Stationery / books",
        "emoji": "✏️",
        "family": "goods",
        "mobile": False,
        "hints": ["stationery", "stationary", "book", "books", "copy", "register",
                  "pen", "xerox", "photostat"],
    },
    "cloth": {
        "label": "Kapda / readymade",
        "emoji": "👕",
        "family": "goods",
        "mobile": False,
        "hints": ["kapda", "cloth", "readymade", "garment", "vastra", "saree",
                  "suit", "hosiery"],
    },
    "agri": {
        "label": "Beej / khaad",
        "emoji": "🌾",
        "family": "goods",
        "mobile": False,
        "hints": ["beej", "khaad", "seed", "fertilizer", "pesticide", "krishi",
                  "agri", "nursery"],
    },
    "sabzi": {
        # Goods that moves — the reason `mobile` and `family` are separate
        # flags rather than one.
        "label": "Sabzi / fal thela",
        "emoji": "🥬",
        "family": "goods",
        "mobile": True,
        "hints": ["sabzi", "subzi", "vegetable", "fruit", "fal", "phal", "mandi"],
    },
    "dukaan": {
        "label": "Aur koi dukaan",
        "emoji": "🛍️",
        "family": "goods",
        "mobile": False,
        "hints": ["dukaan", "shop", "store"],
    },

    # --- Kaam: shops that do things --------------------------------------
    "repair": {
        "label": "Repair shop",
        "emoji": "🔧",
        "family": "services",
        "mobile": False,
        "hints": ["repair", "marammat", "servicing", "mistri", "mechanic",
                  "workshop", "welding", "winding", "denting"],
    },
    "mobile_repair": {
        "label": "Mobile repair",
        "emoji": "📲",
        "family": "services",
        "mobile": False,
        "hints": ["mobile repair", "phone repair", "screen", "mobile service"],
    },
    "cycle": {
        "label": "Cycle / bike repair",
        "emoji": "🚲",
        "family": "services",
        "mobile": False,
        "hints": ["cycle", "bicycle", "puncture", "pancher", "bike", "scooter",
                  "garage", "tyre"],
    },
    "tailor": {
        "label": "Darzi / silai",
        "emoji": "✂️",
        "family": "services",
        "mobile": False,
        "hints": ["darzi", "tailor", "silai", "silai kadhai", "boutique",
                  "alteration"],
    },
    "salon": {
        "label": "Salon / parlour",
        "emoji": "💇",
        "family": "services",
        "mobile": False,
        "hints": ["salon", "saloon", "parlour", "parlor", "barber", "naai",
                  "hajaam", "beauty"],
    },
    "kaam": {
        "label": "Aur koi kaam",
        "emoji": "🛠️",
        "family": "services",
        "mobile": False,
        "hints": ["kaam", "service", "labour"],
    },
}

DEFAULT_KIND = "other"

# Picker order, grouped by family. Food first because that's where the data
# is today, not because it outranks the rest.
KIND_ORDER = [
    # Khaana
    "thela", "chinese", "chaat", "chai", "juice", "dhaba", "sweets",
    "bakery", "tiffin", "restaurant", "other",
    # Saamaan
    "kirana", "hardware", "electrical", "electronics", "medical",
    "stationery", "cloth", "agri", "sabzi", "dukaan",
    # Kaam
    "repair", "mobile_repair", "cycle", "tailor", "salon", "kaam",
]


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


def kind_family(value: str | None) -> str:
    return KINDS[normalise_kind(value)].get("family", DEFAULT_FAMILY)


def is_perishable(value: str | None) -> bool:
    """Does this kind's listing go off if nobody confirms it?

    True for food, where the answer to "is it there" changes by the hour.
    False for a shop and for a capability, where it changes by the year — and
    where decaying the listing would throw away the only record anyone has.
    """
    return FAMILIES[kind_family(value)]["perishable"]


def family_label(value: str | None) -> str:
    return FAMILIES[kind_family(value)]["label"]


def kind_list() -> list[dict]:
    """Kinds in picker order, shaped for the client."""
    return [
        {"kind": k, "label": KINDS[k]["label"], "emoji": KINDS[k]["emoji"],
         "mobile": KINDS[k]["mobile"], "family": KINDS[k].get("family", DEFAULT_FAMILY)}
        for k in KIND_ORDER
    ]


def family_list() -> list[dict]:
    """Families in picker order, each with the kinds under it."""
    return [
        {
            "family": f,
            "label": FAMILIES[f]["label"],
            "emoji": FAMILIES[f]["emoji"],
            "perishable": FAMILIES[f]["perishable"],
            "kinds": [k for k in KIND_ORDER
                      if KINDS[k].get("family", DEFAULT_FAMILY) == f],
        }
        for f in FAMILIES
    ]


def normalise_family(value: str | None) -> str:
    key = (value or "").strip().lower()
    return key if key in FAMILIES else ""


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

    # --- Saamaan ---------------------------------------------------------
    # Deliberately coarse. These exist to group a shop's list on a card and to
    # give search a second word to match on — not to be an inventory system.
    "Hardware": [
        "cement", "seement", "tanki", "water tank", "sintex", "pipe", "pvc",
        "tap", "nal", "fitting", "sariya", "brick", "eent", "tiles", "plywood", "nail",
        "keel", "screw", "hinge", "lock", "tala", "paint", "putty", "brush",
        "hammer", "sink", "basin", "toilet seat",
    ],
    "Electrical": [
        "wire", "taar", "bulb", "led", "tubelight", "switch", "socket", "board",
        "holder", "mcb", "fan", "pankha", "cooler", "geyser", "inverter",
        "battery", "solar panel", "solar plate", "submersible", "starter",
        "capacitor", "extension",
    ],
    "Electronics": [
        "charger", "cable", "adapter", "mobile", "phone", "smartphone", "keypad",
        "modem", "router", "wifi", "dish", "set top box", "remote", "earphone",
        "headphone", "speaker", "memory card", "pendrive", "laptop", "mouse",
        "keyboard", "printer", "cctv",
    ],
    "Household": [
        "bucket", "balti", "mug", "bartan", "utensil", "plate", "thali",
        "cooker", "kadhai", "tawa", "broom", "jhadu", "soap", "sabun",
        "detergent", "surf", "phenyl", "mat", "rope", "rassi", "plastic",
        "container", "tiffin box", "bottle",
    ],
    "Stationery": [
        "pen", "pencil", "notebook", "copy", "register", "file", "folder",
        "chart", "glue", "eraser", "rubber", "sharpener", "scale", "ink",
        "stapler", "envelope", "sketch",
    ],
    "Medicine": [
        "tablet", "capsule", "syrup", "dawa", "dawai", "medicine", "ointment",
        "bandage", "band aid", "dettol", "mask", "sanitizer", "thermometer",
        "injection", "drip", "glucose",
    ],
    "Clothing": [
        "shirt", "pant", "kapda", "cloth", "saree", "sari", "suit", "kurta",
        "banyan", "vest", "socks", "towel", "chaddar", "bedsheet", "blanket",
        "rajai", "sweater", "jacket", "shoes", "chappal", "slipper",
    ],
    "Farming": [
        "beej", "seed", "khaad", "urea", "fertilizer", "pesticide", "sprayer",
        "kudal", "phawda", "sickle", "hansiya", "tarpaulin", "drip",
    ],

    # --- Kaam ------------------------------------------------------------
    # A capability, not a thing on a shelf. Items in this bucket are the ones
    # carrying kind = "service".
    "Repairs": [
        "repair", "marammat", "servicing", "service", "welding", "winding",
        "puncture", "pancher", "denting", "painting", "installation",
        "silai", "tailoring", "alteration", "sharpening", "key making",
        "rewinding", "overhaul", "recharge", "xerox", "photostat", "lamination",
    ],
    # Hint-less on purpose: reachable only as the fallback for a goods item
    # whose name matched nothing.
    "Aur saamaan": [],
}

# Where an unrecognised name lands, per family. Without this every unmatched
# hardware item was filed under "Fast food" — the old default from when the
# only items in the app were dishes.
DEFAULT_CATEGORY = "Fast food"
FAMILY_DEFAULT_CATEGORY = {
    "food": "Fast food",
    "goods": "Aur saamaan",
    "services": "Repairs",
}

CATEGORY_NAMES = list(CATEGORIES.keys())


def suggest_category(name: str, family: str = "") -> str:
    """Best-guess category for an item name.

    Longest hint wins, so "chilli potato" doesn't get claimed by a shorter
    match somewhere else in the table, and "solar panel" beats a bare "panel".
    `family` only decides the fallback when nothing matches at all.
    """
    fallback = FAMILY_DEFAULT_CATEGORY.get(normalise_family(family) or "", DEFAULT_CATEGORY)
    text = (name or "").strip().lower()
    if not text:
        return fallback
    best_category, best_len = "", 0
    for category, hints in CATEGORIES.items():
        for hint in hints:
            if hint in text and len(hint) > best_len:
                best_category, best_len = category, len(hint)
    return best_category or fallback


def normalise_category(value: str | None, name: str = "", family: str = "") -> str:
    """Keep a known category, otherwise re-derive one from the item name."""
    candidate = (value or "").strip()
    for known in CATEGORY_NAMES:
        if candidate.lower() == known.lower():
            return known
    return suggest_category(name or candidate, family)


# ---------------------------------------------------------------------------
# Product or service
# ---------------------------------------------------------------------------
# The half of the catalogue nobody has written down. A shop's stock is true for
# a week; "they repair watches here" is true for years, costs nothing to keep
# accurate, and is exactly what you cannot find out today without walking in
# and asking.

ITEM_PRODUCT = "product"
ITEM_SERVICE = "service"
ITEM_KINDS = (ITEM_PRODUCT, ITEM_SERVICE)

# Words that make an entry a capability rather than a thing on a shelf.
SERVICE_WORDS = {
    "repair", "repairing", "marammat", "servicing", "service", "welding",
    "winding", "rewinding", "puncture", "pancher", "denting", "painting",
    # Not "fitting": in a hardware shop that's a thing in a box ("pipe
    # fitting", "tanki fitting"), not a job someone does for you.
    "installation", "install", "silai", "stitching", "tailoring",
    "alteration", "sharpening", "polish", "polishing", "cleaning", "washing",
    "xerox", "photostat", "lamination", "binding", "recharge", "overhaul",
}


def normalise_item_kind(value: str | None) -> str:
    key = (value or "").strip().lower()
    return key if key in ITEM_KINDS else ITEM_PRODUCT


def suggest_item_kind(name: str, given: str | None = None) -> str:
    """Product unless the name says otherwise.

    An explicit answer always wins — this only guesses when the client didn't
    say, which is the common case for a surveyor typing "watch repair" into a
    list of things a shop does.
    """
    if (given or "").strip().lower() in ITEM_KINDS:
        return given.strip().lower()
    words = set((name or "").lower().replace("-", " ").split())
    return ITEM_SERVICE if words & SERVICE_WORDS else ITEM_PRODUCT


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

    # --- Saamaan ---------------------------------------------------------
    # Same job as the food groups above: these are different names for one
    # thing, not misspellings, so fuzzy correction can't reach them.
    ["water tanki", "tanki", "water tank", "paani ki tanki", "sintex"],
    ["charger", "charging cable", "adapter", "charger cable"],
    ["modem", "router", "wifi router", "wifi"],
    ["solar panel", "solar plate", "solar"],
    ["inverter", "invertor", "ups"],
    ["battery", "batery", "cell"],
    ["bulb", "led bulb", "lamp", "light"],
    ["wire", "taar", "cable"],
    ["cement", "seement", "simenr", "siment"],
    ["paint", "distemper", "rang", "putty"],
    ["pipe", "paip", "pvc pipe", "nali"],
    ["kapda", "cloth", "fabric", "material"],
    ["dawa", "dawai", "medicine", "tablet"],
    # No "kaapi" here — it already means coffee, and a word in two groups
    # silently merges them (searching it would return chai tapris *and*
    # stationery shops).
    ["copy", "notebook", "register"],
    ["jhadu", "broom", "jharu"],
    ["bartan", "utensils", "utensil", "bhande"],
    ["balti", "bucket"],
    ["beej", "seed", "seeds"],
    ["khaad", "fertilizer", "urea", "khad"],
    ["chappal", "slipper", "sandal", "footwear"],

    # --- Kaam ------------------------------------------------------------
    ["repair", "marammat", "banwana", "repairing"],
    ["watch repair", "ghadi repair", "ghadi", "watch"],
    ["mobile repair", "phone repair", "screen repair", "mobile thik"],
    ["puncture", "pancher", "punchar"],
    ["silai", "tailoring", "stitching", "darzi", "tailor"],
    ["welding", "welder", "welding kaam"],
    ["xerox", "photostat", "photocopy"],
    ["haircut", "baal katna", "barber", "naai", "salon"],
]

# word -> every word meaning the same thing, built once at import.
#
# A word may appear in only one group. Two groups sharing a word quietly merge
# them — "kaapi" in both the coffee and the notebook group would make one
# search return chai tapris and stationery shops — and the failure shows up as
# bad results, never as an error. Cheap to assert at import, so assert it.
SYNONYMS: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    for _word in _group:
        if _word in SYNONYMS:
            raise ValueError(
                f"synonym {_word!r} is in two groups; merging them would join "
                f"unrelated searches"
            )
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


# Chips on the home screen — what people actually walk out to get.
#
# Split per family because the chip row follows the tab: someone on "Saamaan"
# is not helped by a chip for jalebi. Every chip has to be a word the category
# table already knows, or it lands in the fallback bucket and the chip quietly
# searches for something the app can't classify (test_smoke.py asserts this).
POPULAR_BY_FAMILY: dict[str, list[str]] = {
    "food": [
        "Momos", "Chowmein", "Golgappe", "Chai", "Samosa", "Maggi", "Roll",
        "Chole bhature", "Dosa", "Paratha", "Jalebi", "Vada pav", "Biryani",
        "Pav bhaji", "Lassi", "Ice cream",
    ],
    "goods": [
        "Water tanki", "Cement", "Pipe", "Paint", "Wire", "Bulb", "Switch",
        "Charger", "Inverter", "Solar panel", "Battery", "Copy", "Dawai",
        "Bucket", "Chappal", "Beej",
    ],
    "services": [
        "Ghadi repair", "Mobile repair", "Puncture", "Motor winding", "Welding",
        "Silai", "Xerox", "Painting", "Servicing",
    ],
}

# The food list under its old name — the chip row falls back to this when no
# family tab is active, and it keeps the original meaning for existing callers.
POPULAR = POPULAR_BY_FAMILY["food"]
