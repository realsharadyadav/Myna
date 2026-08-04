"""Generated demo thele, for trying the app before any real ones exist.

Two things make this useful rather than decorative:

- **It lands around you.** Sample data a thousand kilometres away tells you
  nothing about "paas me kya mil raha hai", so the generator takes the
  browser's coordinates and scatters thele within walking distance of them.
- **It isn't uniform.** Real listings differ in the ways that drive the UI:
  some carts are out right now and some come on Thursdays, some were confirmed
  today and some three weeks ago, one or two have been reported. A dataset
  where every row looks the same can't show you whether the ranking works.
"""
import random
from datetime import datetime, timedelta

from . import food, models, schedule

SURNAMES = [
    "Sharma", "Verma", "Gupta", "Yadav", "Singh", "Patel", "Shah", "Desai",
    "Joshi", "Iyer", "Rao", "Nair", "Reddy", "Jain", "Chopra", "Malhotra",
    "Bansal", "Kohli", "Anand", "Bedi", "Chavan", "Bhosale", "Kadam", "Shinde",
    "Raju", "Munna", "Chotu", "Guddu", "Pappu", "Bablu",
]

# What a thela of each kind is called, and what's actually on its board.
# Prices are the rough street range in rupees — the generator picks within it,
# rounded to the nearest 5, because no board says "₹47".
BLUEPRINTS: dict[str, dict] = {
    "chinese": {
        "names": ["Chinese Corner", "Fast Food", "Chowmein Point", "Momos Junction"],
        "menu": [("Veg Chowmein", 40, 70), ("Steam Momos", 40, 60),
                 ("Fried Momos", 50, 80), ("Spring Roll", 50, 80),
                 ("Manchurian", 60, 100), ("Chilli Potato", 60, 90),
                 ("Veg Fried Rice", 50, 90), ("Hot & Sour Soup", 40, 60)],
    },
    "chaat": {
        "names": ["Chaat Bhandar", "Chaat Corner", "Golgappe wala", "Tikki Center"],
        "menu": [("Golgappe", 20, 40), ("Aloo Tikki", 30, 50), ("Bhelpuri", 25, 45),
                 ("Dahi Puri", 40, 60), ("Sev Puri", 30, 50), ("Samosa", 15, 25),
                 ("Raj Kachori", 50, 80), ("Papdi Chaat", 40, 60)],
    },
    "chai": {
        "names": ["Chai Tapri", "Tea Stall", "Chai Point", "Kulhad Chai"],
        "menu": [("Masala Chai", 10, 20), ("Kulhad Chai", 15, 25),
                 ("Coffee", 20, 40), ("Bun Maska", 20, 40), ("Rusk", 10, 20),
                 ("Cream Roll", 20, 30)],
    },
    "thela": {
        "names": ["Momos thela", "Anda thela", "Sandwich thela", "Chowmein thela"],
        "menu": [("Steam Momos", 40, 60), ("Egg Roll", 40, 70),
                 ("Bread Omelette", 30, 50), ("Anda Bhurji", 50, 80),
                 ("Veg Sandwich", 30, 60), ("Maggi", 30, 50)],
    },
    "juice": {
        "names": ["Juice Center", "Shikanji wala", "Ganne ka Ras", "Lassi Corner"],
        "menu": [("Nimbu Shikanji", 20, 40), ("Sweet Lassi", 40, 70),
                 ("Ganne ka Ras", 20, 40), ("Mosambi Juice", 40, 70),
                 ("Nariyal Pani", 40, 60), ("Cold Coffee", 50, 90)],
    },
    "dhaba": {
        "names": ["Dhaba", "Bhojanalya", "Punjabi Dhaba", "Highway Dhaba"],
        "menu": [("Dal Fry", 80, 130), ("Butter Roti", 10, 20),
                 ("Paneer Butter Masala", 150, 250), ("Rajma Chawal", 90, 140),
                 ("Veg Thali", 100, 180), ("Aloo Paratha", 40, 70),
                 ("Chole Bhature", 60, 100)],
    },
    "sweets": {
        "names": ["Sweets", "Mithai Bhandar", "Halwai", "Jalebi wala"],
        "menu": [("Jalebi", 40, 80), ("Gulab Jamun", 40, 80), ("Rasgulla", 40, 80),
                 ("Kaju Katli", 200, 400), ("Motichoor Laddu", 40, 80),
                 ("Gajar Halwa", 60, 120)],
    },
    "bakery": {
        "names": ["Bakery", "Cake Shop", "Bake House"],
        "menu": [("Veg Puff", 20, 35), ("Cream Roll", 20, 40), ("Pastry", 40, 80),
                 ("Khari Biscuit", 20, 40), ("Bread", 30, 50)],
    },
    "restaurant": {
        "names": ["Family Restaurant", "Cafe", "Kitchen"],
        "menu": [("Veg Biryani", 120, 200), ("Butter Naan", 30, 60),
                 ("Paneer Tikka", 150, 250), ("Masala Dosa", 70, 120),
                 ("Veg Fried Rice", 90, 150)],
    },
}

KIND_WEIGHTS = {
    "chinese": 5, "chaat": 5, "chai": 4, "thela": 4, "juice": 3,
    "dhaba": 3, "sweets": 2, "bakery": 2, "restaurant": 2,
}

STREETS = [
    "Gali no. {n}", "Sector {n} market", "Station road", "Bus stand ke saamne",
    "School ke paas", "Main market", "Sabzi mandi", "Park ke corner pe",
    "Hospital gate", "Metro station gate {n}", "Chowk", "Petrol pump ke paas",
]

# Roughly 1 km at Indian latitudes. Sample thele spread over a walkable area
# rather than a single point, so distance sorting has something to sort.
_DEG_PER_KM = 0.009


def _price(low: int, high: int, rng: random.Random) -> float:
    return float(round(rng.randint(low, high) / 5) * 5)


def _scatter(lat: float, long: float, rng: random.Random, radius_km: float) -> tuple[float, float]:
    return (
        lat + rng.uniform(-radius_km, radius_km) * _DEG_PER_KM,
        long + rng.uniform(-radius_km, radius_km) * _DEG_PER_KM,
    )


def build(lat: float, long: float, count: int = 50, radius_km: float = 2.0,
          seed: int | None = None) -> list[models.Shop]:
    """Generate `count` thele around (lat, long), menus and all.

    Returns unsaved Shop objects with their items and stops attached — the
    caller commits, so this stays testable without a database.
    """
    rng = random.Random(seed)
    kinds = list(KIND_WEIGHTS)
    weights = [KIND_WEIGHTS[k] for k in kinds]
    now = datetime.utcnow()

    shops: list[models.Shop] = []
    used_names: set[str] = set()
    for index in range(count):
        kind = rng.choices(kinds, weights=weights)[0]
        blueprint = BLUEPRINTS[kind]

        name = f"{rng.choice(SURNAMES)} {rng.choice(blueprint['names'])}"
        while name in used_names:
            name = f"{rng.choice(SURNAMES)} {rng.choice(blueprint['names'])}"
        used_names.add(name)

        shop_lat, shop_long = _scatter(lat, long, rng, radius_km)
        mobile = food.is_mobile_kind(kind) or rng.random() < 0.2

        # Freshness spread on purpose: mostly recent, a long tail of stale, and
        # a couple nobody has ever confirmed — so the trust styling and the
        # ranking have something to actually distinguish.
        confirmed = rng.random()
        if confirmed < 0.1:
            seen_yes, last_seen = 0, None
        else:
            days_ago = rng.choices([0, 1, 3, 8, 20], weights=[5, 3, 3, 2, 1])[0]
            seen_yes = rng.randint(1, 12)
            last_seen = now - timedelta(days=days_ago, hours=rng.randint(0, 12))

        shop = models.Shop(
            name=name,
            lat=shop_lat,
            long=shop_long,
            address=rng.choice(STREETS).format(n=rng.randint(1, 18)),
            food_kind=kind,
            shop_type="mobile" if mobile else "fixed",
            added_by="sample-data",
            seen_yes=seen_yes,
            last_seen_at=last_seen,
        )

        dishes = rng.sample(blueprint["menu"], k=rng.randint(3, min(6, len(blueprint["menu"]))))
        for dish, low, high in dishes:
            shop.items.append(models.Item(
                name=dish,
                category=food.suggest_category(dish),
                # Not every board writes its rates, and the app has to look
                # right when a price is missing.
                price=_price(low, high, rng) if rng.random() < 0.85 else 0.0,
            ))

        if mobile:
            for _ in range(rng.randint(1, 2)):
                stop_lat, stop_long = _scatter(lat, long, rng, radius_km)
                start = rng.choice([6, 7, 8, 11, 16, 17, 18, 19])
                shop.stops.append(models.ShopStop(
                    lat=stop_lat,
                    long=stop_long,
                    address=rng.choice(STREETS).format(n=rng.randint(1, 18)),
                    # Mostly daily rounds with a few weekly ones, which is what
                    # makes "here now" vs "comes on Thursday" visible.
                    day_of_week=rng.choice(
                        [schedule.EVERY_DAY] * 4 + list(range(7))
                    ),
                    start_time=f"{start:02d}:00",
                    end_time=f"{min(start + rng.randint(3, 6), 23):02d}:00",
                ))

        # A couple of reported listings, so the Reports tab isn't empty either.
        if index % 17 == 16:
            shop.report_count = 1
            shop.reports.append(models.ShopReport(
                device_id="sample-data", reason="wrong",
                note="Sample entry — rates purane lag rahe hain.",
            ))

        shops.append(shop)
    return shops
