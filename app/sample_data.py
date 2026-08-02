"""Sample/demo data for Myna — used by seed_data.py and the admin CSV template."""
import random

# ---------------------------------------------------------------------------
# Hand-curated anchor shops
# ---------------------------------------------------------------------------
CURATED = [
    {
        "name": "Sharma General Store",
        "shopkeeper": "Ramesh Sharma",
        "lat": 19.0760,
        "long": 72.8777,
        "address": "Shop 4, Link Road, Andheri West, Mumbai",
        "phone": "9820012345",
        "items": [
            ("Parle-G Gold Biscuits 100g", "Snacks"),
            ("Tata Salt 1kg", "Grocery"),
            ("Aashirvaad Atta 5kg", "Grocery"),
            ("Maggi Noodles 70g", "Instant Food"),
            ("Surf Excel 1kg", "Household"),
            ("Colgate MaxFresh 100g", "Personal Care"),
        ],
    },
    {
        "name": "Patel Supermarket",
        "shopkeeper": "Nita Patel",
        "lat": 19.0700,
        "long": 72.8700,
        "address": "Marol Market, Marol, Andheri East, Mumbai",
        "phone": "9830012345",
        "items": [
            ("Parle-G Original 250g", "Snacks"),
            ("Amul Butter 500g", "Dairy"),
            ("Milk 500ml Amul Taaza", "Dairy"),
            ("Britannia Bourbon Biscuits", "Snacks"),
            ("Fortune Sunflower Oil 1L", "Grocery"),
            ("Dettol Soap 100g", "Personal Care"),
        ],
    },
    {
        "name": "Khan Kirana Bhandar",
        "shopkeeper": "Abdul Khan",
        "lat": 19.0820,
        "long": 72.8880,
        "address": "Jogeshwari West Market, Mumbai",
        "phone": "9840012345",
        "items": [
            ("Tata Tea Gold 250g", "Beverages"),
            ("Red Label Chai 500g", "Beverages"),
            ("Basmati Rice 1kg", "Grocery"),
            ("Toor Dal 1kg", "Grocery"),
            ("Parle-G Glucose 400g", "Snacks"),
        ],
    },
    {
        "name": "Verma Medical & General",
        "shopkeeper": "Sunil Verma",
        "lat": 19.0600,
        "long": 72.8600,
        "address": "Vile Parle East, Mumbai",
        "phone": "9850012345",
        "items": [
            ("Dolo 650 Tablets", "Pharmacy"),
            ("Band-Aid Strips", "Pharmacy"),
            ("Crocin 650", "Pharmacy"),
            ("Odomos Mosquito Repellent", "Personal Care"),
            ("Vicks VapoRub", "Pharmacy"),
        ],
    },
    {
        "name": "Mumbai Fresh Mart",
        "shopkeeper": "Priya Desai",
        "lat": 19.1000,
        "long": 72.9000,
        "address": "Goregaon West, Mumbai",
        "phone": "9860012345",
        "items": [
            ("Bananas 1kg", "Fruits"),
            ("Apples 1kg", "Fruits"),
            ("Tomatoes 1kg", "Vegetables"),
            ("Onions 1kg", "Vegetables"),
            ("Coriander Bunch", "Vegetables"),
            ("Lemon 500g", "Vegetables"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Generators for additional shops
# ---------------------------------------------------------------------------
SURNAMES = [
    "Sharma", "Patel", "Khan", "Verma", "Desai", "Gupta", "Singh", "Mehta",
    "Agarwal", "Joshi", "Iyer", "Rao", "Nair", "Reddy", "Jain", "Chopra",
    "Malhotra", "Bhatia", "Kapoor", "Saxena", "Tiwari", "Mishra", "Trivedi",
    "Pandey", "Chawla", "Bansal", "Kohli", "Talwar", "Anand", "Bedi",
    "Gill", "Dhillon", "Bajwa", "Kaur", "Sheikh", "Ansari", "Siddiqui",
    "Naik", "Kamat", "Sawant", "Mhatre", "Pawar", "Patil", "Jadhav",
    "Chavan", "Bhosale", "Kadam", "Gaikwad", "Shinde", "Pradhan",
]

FIRST_NAMES = [
    "Ramesh", "Suresh", "Mahesh", "Dinesh", "Rajesh", "Amit", "Sunil",
    "Nitin", "Sanjay", "Vijay", "Anil", "Rahul", "Rohan", "Arjun",
    "Kiran", "Priya", "Neha", "Pooja", "Anita", "Smita", "Kavita",
    "Meena", "Rekha", "Usha", "Geeta", "Manoj", "Prakash", "Deepak",
    "Ashok", "Rajendra", "Vikram", "Gaurav", "Abhishek", "Nikhil",
]

SHOP_SUFFIXES = [
    "General Store", "Kirana Bhandar", "Super Market", "Provision Store",
    "Super Bazar", "Departmental Store", "Mini Mart", "Grocery & General",
    "Stores", "Super Mart",
]

NEIGHBORHOODS = [
    "Andheri West", "Andheri East", "Jogeshwari West", "Jogeshwari East",
    "Goregaon West", "Goregaon East", "Malad West", "Malad East",
    "Kandivali West", "Kandivali East", "Borivali West", "Borivali East",
    "Dahisar", "Bandra West", "Khar West", "Santacruz West", "Vile Parle West",
    "Juhu", "Versova", "Marol", "Powai", "Bhandup", "Mulund West",
    "Mulund East", "Chembur", "Ghatkopar West", "Kurla", "Sion", "Dadar",
    "Matunga", "Worli", "Lower Parel", "Byculla", "Colaba", "Fort",
    "Parel", "Sewri", "Wadala", "Mahim", "Prabhadevi", "Lokhandwala",
    "Oshiwara", "Amboli", "Chakala", "MIDC Andheri",
]

NEIGHBORHOOD_COORDS = {
    "Borivali West": (19.2300, 72.8560), "Borivali East": (19.2280, 72.8700),
    "Dahisar": (19.2450, 72.8720), "Kandivali West": (19.2000, 72.8380),
    "Kandivali East": (19.1970, 72.8650), "Malad West": (19.1800, 72.8450),
    "Malad East": (19.1760, 72.8660), "Goregaon West": (19.1640, 72.8480),
    "Goregaon East": (19.1600, 72.8700), "Jogeshwari West": (19.1400, 72.8500),
    "Jogeshwari East": (19.1350, 72.8680), "Andheri West": (19.1190, 72.8460),
    "Andheri East": (19.1130, 72.8690), "Versova": (19.1350, 72.8160),
    "Juhu": (19.1070, 72.8260), "Lokhandwala": (19.1160, 72.8380),
    "Oshiwara": (19.1480, 72.8580), "Amboli": (19.1290, 72.8510),
    "Marol": (19.1060, 72.8760), "Chakala": (19.1120, 72.8520),
    "MIDC Andheri": (19.1160, 72.8770), "Powai": (19.1170, 72.9060),
    "Bhandup": (19.1490, 72.9350), "Mulund West": (19.1700, 72.9450),
    "Mulund East": (19.1680, 72.9600), "Bandra West": (19.0550, 72.8370),
    "Khar West": (19.0720, 72.8320), "Santacruz West": (19.0830, 72.8380),
    "Vile Parle West": (19.0990, 72.8410), "Mahim": (19.0450, 72.8400),
    "Prabhadevi": (19.0170, 72.8290), "Dadar": (19.0170, 72.8440),
    "Matunga": (19.0290, 72.8500), "Worli": (19.0040, 72.8240),
    "Lower Parel": (18.9990, 72.8250), "Parel": (19.0000, 72.8360),
    "Byculla": (18.9800, 72.8350), "Sewri": (19.0030, 72.8600),
    "Wadala": (19.0160, 72.8600), "Sion": (19.0430, 72.8610),
    "Kurla": (19.0750, 72.8820), "Ghatkopar West": (19.0860, 72.9000),
    "Chembur": (19.0500, 72.8950), "Colaba": (18.9060, 72.8150),
    "Fort": (18.9350, 72.8330),
}

PRODUCTS = [
    ("Parle-G Biscuits 100g", "Snacks"),
    ("Britannia Good Day Biscuits", "Snacks"),
    ("Kurkure Masala", "Snacks"),
    ("Lays Indian Masala", "Snacks"),
    ("Uncle Chips", "Snacks"),
    ("Haldiram Bhujia", "Snacks"),
    ("Cadbury Dairy Milk 45g", "Confectionery"),
    ("Parle Mango Bite", "Confectionery"),
    ("Alpenliebe Candies", "Confectionery"),
    ("Amul Butter 500g", "Dairy"),
    ("Amul Cheese 200g", "Dairy"),
    ("Mother Dairy Milk 500ml", "Dairy"),
    ("Amul Taaza Milk 500ml", "Dairy"),
    ("Eggs (Half Dozen)", "Dairy"),
    ("Nescafe 50g", "Beverages"),
    ("Tata Tea Gold 250g", "Beverages"),
    ("Bournvita 500g", "Beverages"),
    ("Red Label Chai 500g", "Beverages"),
    ("Coca-Cola 750ml", "Beverages"),
    ("Thums Up 750ml", "Beverages"),
    ("Aashirvaad Atta 5kg", "Grocery"),
    ("Fortune Sunflower Oil 1L", "Grocery"),
    ("Tata Salt 1kg", "Grocery"),
    ("Aashirvaad Besan 1kg", "Grocery"),
    ("Toor Dal 1kg", "Grocery"),
    ("Basmati Rice 1kg", "Grocery"),
    ("Sugar 1kg", "Grocery"),
    ("Maggi Noodles 70g", "Instant Food"),
    ("Top Ramen Masala", "Instant Food"),
    ("Yippee Noodles", "Instant Food"),
    ("Dettol Soap 100g", "Personal Care"),
    ("Lifebuoy Soap 100g", "Personal Care"),
    ("Colgate Toothpaste 100g", "Personal Care"),
    ("Clinic Plus Shampoo", "Personal Care"),
    ("Hand Sanitizer 500ml", "Personal Care"),
    ("Surf Excel 1kg", "Household"),
    ("Tide Detergent 1kg", "Household"),
    ("Vim Dishwash Bar", "Household"),
    ("Harpic Toilet Cleaner", "Household"),
    ("Dolo 650 Tablets", "Pharmacy"),
    ("Crocin 650", "Pharmacy"),
    ("Vicks VapoRub", "Pharmacy"),
    ("Band-Aid Strips", "Pharmacy"),
    ("Dettol Antiseptic 100ml", "Pharmacy"),
    ("Bananas 1kg", "Fruits"),
    ("Apples 1kg", "Fruits"),
    ("Oranges 1kg", "Fruits"),
    ("Tomatoes 1kg", "Vegetables"),
    ("Onions 1kg", "Vegetables"),
    ("Potatoes 1kg", "Vegetables"),
]


def build_shops(total: int = 50) -> list[dict]:
    """Build `total` shops (curated + generated). Fixed seed for reproducibility."""
    generated = max(0, total - len(CURATED))
    if generated == 0:
        return CURATED[:total]

    rng = random.Random(42)
    surnames = rng.sample(SURNAMES, generated)
    names = [rng.choice(FIRST_NAMES) for _ in range(generated)]
    neighborhoods = [rng.choice(NEIGHBORHOODS) for _ in range(generated)]

    shops = list(CURATED)
    for i in range(generated):
        surname = surnames[i]
        nb = neighborhoods[i]
        base_lat, base_lon = NEIGHBORHOOD_COORDS[nb]
        lat = round(base_lat + rng.uniform(-0.008, 0.008), 5)
        lon = round(base_lon + rng.uniform(-0.008, 0.008), 5)
        phone = "9" + str(rng.randint(600000000, 999999999))
        shop_num = rng.randint(1, 400)
        items = rng.sample(PRODUCTS, rng.randint(4, 8))
        shops.append({
            "name": f"{surname} {rng.choice(SHOP_SUFFIXES)}",
            "shopkeeper": f"{names[i]} {surname}",
            "lat": lat,
            "long": lon,
            "address": f"Shop {shop_num}, {nb}, Mumbai",
            "phone": phone,
            "items": items,
        })
    return shops


CSV_HEADERS = ["shop_name", "shopkeeper", "lat", "long", "address", "phone", "item_name", "category"]


def shops_to_csv_rows(shops: list[dict]) -> list[dict]:
    """Flatten shops into one CSV row per item (flat format the importer accepts)."""
    rows = []
    for s in shops:
        items = s.get("items") or [("", "")]
        for name, category in items:
            rows.append({
                "shop_name": s["name"],
                "shopkeeper": s.get("shopkeeper", ""),
                "lat": s["lat"],
                "long": s["long"],
                "address": s.get("address", ""),
                "phone": s.get("phone", ""),
                "item_name": name,
                "category": category,
            })
    return rows
