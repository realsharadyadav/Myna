"""Curated category → item catalogue for shopkeeper onboarding.

Typing every product one at a time is the slowest possible way to list a
shop, and it's the step where shopkeepers give up. This module backs the
faster path: ask what *kind* of shop it is ("puja items", "dry fruits",
"vegetables", "spices"), then show the products that category usually
carries as checkboxes so a hundred items go in with a few taps.

Labels are deliberately bilingual where the Hindi word is what people
actually say ("Turmeric (Haldi)"): the stored name then carries both tokens,
so customer searches match whichever word they type — the same reason
app/dishes.py mixes English and Hinglish. Keep that convention when adding
items here.

Nothing in here is enforced — a shopkeeper can still type any item by hand.
This is a starting point, not a fixed taxonomy.
"""

# Each category: key, label shown to the shopkeeper, an emoji for the chip,
# and the products it usually carries. Order matters — the first few
# categories are the ones most kirana shops tick.
CATEGORIES: list[dict] = [
    {
        "key": "grocery",
        "label": "Everyday grocery",
        "emoji": "🛒",
        "items": [
            "Rice (Chawal)", "Basmati Rice", "Wheat Flour (Atta)", "Maida",
            "Sooji (Rava)", "Besan", "Poha", "Sabudana", "Vermicelli (Seviyan)",
            "Sugar (Cheeni)", "Jaggery (Gud)", "Salt (Namak)", "Rock Salt (Sendha Namak)",
            "Tea Leaves (Chai Patti)", "Coffee", "Papad", "Pickle (Achar)",
            "Tomato Ketchup", "Honey (Shahad)", "Vinegar", "Corn Flour",
            "Baking Soda", "Custard Powder", "Dalia",
        ],
    },
    {
        "key": "dals",
        "label": "Dal & pulses",
        "emoji": "🫘",
        "items": [
            "Toor Dal (Arhar)", "Moong Dal", "Chana Dal", "Masoor Dal",
            "Urad Dal", "Moth Dal", "Rajma", "Kabuli Chana (Chole)",
            "Kala Chana", "Lobia (Black Eyed Beans)", "Green Moong (Sabut)",
            "Soya Chunks", "Matar (Dried Peas)",
        ],
    },
    {
        "key": "spices",
        "label": "Spices & masala",
        "emoji": "🌶️",
        "items": [
            "Turmeric (Haldi)", "Red Chilli Powder (Lal Mirch)",
            "Coriander Powder (Dhaniya)", "Cumin Seeds (Jeera)",
            "Mustard Seeds (Sarson/Rai)", "Garam Masala", "Chaat Masala",
            "Sambar Masala", "Chole Masala", "Pav Bhaji Masala",
            "Kitchen King Masala", "Black Pepper (Kali Mirch)",
            "Cardamom (Elaichi)", "Cloves (Laung)", "Cinnamon (Dalchini)",
            "Bay Leaf (Tej Patta)", "Asafoetida (Hing)", "Fenugreek (Methi Dana)",
            "Carom Seeds (Ajwain)", "Fennel (Saunf)", "Kasuri Methi",
            "Dry Mango Powder (Amchur)", "Star Anise (Chakri Phool)",
            "Nutmeg (Jaiphal)", "Saffron (Kesar)", "Ginger Garlic Paste",
        ],
    },
    {
        "key": "puja",
        "label": "Puja items",
        "emoji": "🪔",
        "items": [
            "Agarbatti (Incense Sticks)", "Dhoop Batti", "Camphor (Kapoor)",
            "Cotton Wicks (Batti)", "Diya (Clay Lamp)", "Puja Oil",
            "Desi Ghee for Diya", "Roli", "Kumkum", "Haldi (Puja)",
            "Chandan (Sandalwood Paste)", "Rice for Puja (Akshat)",
            "Kalava (Mauli Dhaga)", "Janeu", "Coconut (Nariyal)",
            "Supari", "Elaichi Dana (Puja)", "Loban", "Havan Samagri",
            "Gangajal", "Panchamrit Items", "Puja Thali", "Bell (Ghanti)",
            "Shankh", "Asan (Puja Mat)", "Idols & Photo Frames",
            "Rudraksha Mala", "Tulsi Mala", "Flower Garland (Mala)",
            "Rangoli Colours", "Kalash", "Matchbox",
        ],
    },
    {
        "key": "dryfruits",
        "label": "Dry fruits & nuts",
        "emoji": "🥜",
        "items": [
            "Almonds (Badam)", "Cashews (Kaju)", "Raisins (Kishmish)",
            "Walnuts (Akhrot)", "Pistachios (Pista)", "Dates (Khajoor)",
            "Dried Figs (Anjeer)", "Apricots (Khubani)", "Makhana (Fox Nuts)",
            "Peanuts (Moongfali)", "Chironji", "Melon Seeds (Magaz)",
            "Pumpkin Seeds", "Sunflower Seeds", "Flax Seeds (Alsi)",
            "Chia Seeds", "Dry Coconut (Copra)", "Mixed Dry Fruit Pack",
        ],
    },
    {
        "key": "vegetables",
        "label": "Vegetables",
        "emoji": "🥬",
        "items": [
            "Potato (Aloo)", "Onion (Pyaz)", "Tomato (Tamatar)",
            "Garlic (Lehsun)", "Ginger (Adrak)", "Green Chilli (Hari Mirch)",
            "Coriander Leaves (Dhaniya Patta)", "Mint (Pudina)",
            "Curry Leaves (Kadi Patta)", "Cauliflower (Gobhi)",
            "Cabbage (Patta Gobhi)", "Brinjal (Baingan)", "Lady Finger (Bhindi)",
            "Bottle Gourd (Lauki)", "Bitter Gourd (Karela)", "Pumpkin (Kaddu)",
            "Capsicum (Shimla Mirch)", "Carrot (Gajar)", "Radish (Mooli)",
            "Beetroot (Chukandar)", "Spinach (Palak)", "Fenugreek Leaves (Methi)",
            "Peas (Matar)", "Cucumber (Kheera)", "Beans (Phali)",
            "Sweet Corn (Bhutta)", "Sweet Potato (Shakarkandi)", "Colocasia (Arbi)",
        ],
    },
    {
        "key": "fruits",
        "label": "Fruits",
        "emoji": "🍎",
        "items": [
            "Banana (Kela)", "Apple (Seb)", "Orange (Santra)", "Mosambi",
            "Mango (Aam)", "Grapes (Angoor)", "Papaya (Papita)",
            "Pomegranate (Anar)", "Guava (Amrood)", "Watermelon (Tarbooj)",
            "Muskmelon (Kharbooja)", "Pineapple (Ananas)", "Pear (Nashpati)",
            "Chikoo", "Lemon (Nimbu)", "Custard Apple (Sitaphal)",
            "Strawberry", "Kiwi",
        ],
    },
    {
        "key": "oils",
        "label": "Oil & ghee",
        "emoji": "🫗",
        "items": [
            "Mustard Oil (Sarson Tel)", "Refined Sunflower Oil", "Soyabean Oil",
            "Groundnut Oil", "Rice Bran Oil", "Coconut Oil", "Sesame Oil (Til Tel)",
            "Olive Oil", "Desi Ghee", "Vanaspati Ghee", "Butter (Makhan)",
        ],
    },
    {
        "key": "dairy",
        "label": "Dairy, bread & eggs",
        "emoji": "🥛",
        "items": [
            "Milk (Doodh)", "Curd (Dahi)", "Paneer", "Cheese Slices",
            "Butter", "Fresh Cream", "Buttermilk (Chaach)", "Lassi",
            "Flavoured Milk", "Milk Powder", "Condensed Milk", "Khoya (Mawa)",
            "Bread", "Pav", "Bun", "Rusk (Toast)", "Eggs (Anda)",
        ],
    },
    {
        "key": "snacks",
        "label": "Snacks & biscuits",
        "emoji": "🍪",
        "items": [
            "Parle-G Biscuits", "Marie Biscuits", "Good Day Biscuits",
            "Bourbon / Cream Biscuits", "Krackjack / Monaco", "Rusk",
            "Namkeen (Mixture)", "Bhujia", "Aloo Bhujia", "Moong Dal Namkeen",
            "Chips (Lays / Kurkure)", "Popcorn", "Wafers", "Cake / Muffin",
            "Chocolate (Dairy Milk)", "Toffee & Candy", "Chewing Gum",
            "Instant Noodles (Maggi)", "Pasta", "Soan Papdi", "Gujiya / Mathri",
        ],
    },
    {
        "key": "beverages",
        "label": "Cold drinks & beverages",
        "emoji": "🥤",
        "items": [
            "Cold Drink (Coke / Pepsi)", "Sprite / Limca", "Frooti / Maaza",
            "Fruit Juice", "Packaged Water Bottle", "Soda", "Energy Drink",
            "Glucose Powder (Glucon-D)", "Health Drink (Horlicks / Bournvita)",
            "Rooh Afza / Sharbat", "Lemon Soft Drink Concentrate",
            "Iced Tea", "Buttermilk Packet",
        ],
    },
    {
        "key": "cleaning",
        "label": "Cleaning & household",
        "emoji": "🧹",
        "items": [
            "Detergent Powder (Surf / Nirma)", "Detergent Bar", "Liquid Detergent",
            "Dishwash Bar (Vim)", "Dishwash Liquid", "Scrub Pad",
            "Floor Cleaner (Lizol)", "Toilet Cleaner (Harpic)", "Glass Cleaner",
            "Phenyl", "Bleach", "Naphthalene Balls", "Broom (Jhadu)",
            "Mop / Wiper", "Dustbin", "Garbage Bags", "Aluminium Foil",
            "Cling Film", "Mosquito Coil / Repellent", "Room Freshener",
            "Candles", "Matchbox", "Bulb / LED", "Batteries",
        ],
    },
    {
        "key": "personalcare",
        "label": "Personal care",
        "emoji": "🧼",
        "items": [
            "Bath Soap", "Handwash", "Shampoo", "Conditioner", "Hair Oil",
            "Toothpaste", "Toothbrush", "Tooth Powder (Manjan)", "Mouthwash",
            "Face Wash", "Body Lotion", "Cold Cream", "Petroleum Jelly",
            "Talcum Powder", "Deodorant", "Perfume / Attar", "Shaving Cream",
            "Razor / Blade", "Hair Dye (Mehendi)", "Comb", "Sanitary Pads",
            "Tissue Paper", "Toilet Paper", "Nail Cutter",
        ],
    },
    {
        "key": "baby",
        "label": "Baby care",
        "emoji": "🍼",
        "items": [
            "Diapers", "Baby Wipes", "Baby Soap", "Baby Shampoo",
            "Baby Oil (Malish)", "Baby Powder", "Baby Lotion",
            "Baby Food / Cerelac", "Infant Formula Milk", "Feeding Bottle",
            "Bottle Cleaning Brush", "Baby Rash Cream",
        ],
    },
    {
        "key": "stationery",
        "label": "Stationery & general",
        "emoji": "✏️",
        "items": [
            "Notebook / Register", "A4 Paper", "Pen", "Pencil", "Eraser",
            "Sharpener", "Geometry Box", "Scale (Ruler)", "Marker",
            "Highlighter", "Glue / Fevicol", "Cello Tape", "Stapler & Pins",
            "Envelope", "File / Folder", "Sketch Pens", "Crayons",
            "Chart Paper", "Gift Wrapping Paper", "Carry Bags",
        ],
    },
    {
        "key": "sweets",
        "label": "Sweets & bakery",
        "emoji": "🍬",
        "items": [
            "Laddoo", "Barfi", "Kaju Katli", "Gulab Jamun", "Rasgulla",
            "Jalebi", "Peda", "Soan Papdi", "Milk Cake", "Halwa",
            "Cake", "Pastry", "Cookies", "Patties / Puff", "Samosa",
            "Kachori", "Bread Pakora", "Dry Fruit Sweet Box",
        ],
    },
]

_BY_KEY = {c["key"]: c for c in CATEGORIES}


def _aliases(label: str) -> list[str]:
    """Searchable names for a catalogue entry: "Turmeric (Haldi)" is both
    "turmeric" and "haldi", and either is what a packet might say."""
    import re as _re

    parts = [p.strip().lower() for p in _re.split(r"[()/]", label)]
    return [p for p in parts if len(p) >= 3]


# alias -> category label, longest aliases first so "mustard oil" beats "oil".
# Built once at import: it's ~300 entries and every photo suggestion hits it.
_ALIAS_TO_CATEGORY: list[tuple[str, str]] = sorted(
    {
        alias: cat["label"]
        for cat in reversed(CATEGORIES)          # earlier categories win ties
        for item in cat["items"]
        for alias in _aliases(item)
    }.items(),
    key=lambda pair: -len(pair[0]),
)


def all_categories() -> list[dict]:
    """The full catalogue, ready to serve to the shopkeeper UI."""
    return [
        {
            "key": c["key"],
            "label": c["label"],
            "emoji": c["emoji"],
            "count": len(c["items"]),
            "items": list(c["items"]),
        }
        for c in CATEGORIES
    ]


def category_label(key: str) -> str:
    """Human label for a category key ('' if the key isn't in the catalogue)."""
    cat = _BY_KEY.get(key)
    return cat["label"] if cat else ""


def suggest_category(item_name: str) -> str:
    """Best-effort category label for a free-text item name.

    Used to fill in a category the vision model didn't return, so items added
    from a photo still land in the same buckets as catalogue items instead of
    being uncategorised.
    """
    import re as _re

    needle = (item_name or "").strip().lower()
    if not needle:
        return ""
    for alias, label in _ALIAS_TO_CATEGORY:
        # Word-aware, so "haldi" doesn't match "Haldiram" — the same trap
        # app/routers/search.py guards against.
        if _re.search(rf"(?<![a-z0-9]){_re.escape(alias)}(?![a-z0-9])", needle):
            return label
    return ""
