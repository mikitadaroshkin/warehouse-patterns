"""Synthetic data generator for the retail-sales star-schema demo.

Everything produced here is fabricated from a fixed random seed. There is no
client, proprietary, or real personal data anywhere in this module -- the names,
customers, stores and transactions are invented purely to exercise the modelling
patterns. The generator is deterministic (seeded), so a rebuild reproduces the
same numbers and the query output committed to the README stays honest.

The design intentionally emits the customer dimension as *two source snapshots*
taken six months apart. Roughly a third of customers differ between the two
snapshots (they change segment and/or move city). That change stream is what the
Slowly-Changing-Dimension Type-2 loader in ``scd.py`` turns into versioned
history, and it is what makes the point-in-time analytics meaningful.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

# --- generation parameters (deterministic) ---------------------------------
SEED = 20240117
N_PRODUCTS = 24
N_CUSTOMERS = 200
N_SALES = 5000

SALES_START = dt.date(2024, 1, 1)
SALES_END = dt.date(2025, 6, 30)

# The two source extracts the SCD-2 loader consumes, oldest first.
SNAPSHOT_1 = dt.date(2024, 1, 1)
SNAPSHOT_2 = dt.date(2024, 7, 1)

# Fraction of customers whose tracked attributes change between the snapshots.
CHURN_FRACTION = 0.30

# --- reference vocabularies (all invented) ---------------------------------
CATEGORIES: dict[str, list[str]] = {
    "Electronics": ["Laptops", "Phones", "Audio", "Accessories"],
    "Home & Kitchen": ["Cookware", "Appliances", "Storage"],
    "Sports & Outdoors": ["Fitness", "Camping", "Cycling"],
    "Office Supplies": ["Paper", "Writing", "Organization"],
    "Apparel": ["Footwear", "Outerwear", "Basics"],
}

# Category -> (low, high) unit-price band, in whole currency units.
PRICE_BANDS: dict[str, tuple[int, int]] = {
    "Electronics": (60, 1400),
    "Home & Kitchen": (15, 320),
    "Sports & Outdoors": (25, 650),
    "Office Supplies": (3, 90),
    "Apparel": (12, 240),
}

BRANDS = ["Aster", "Borealis", "Cirrus", "Delphi", "Ember", "Fjord", "Grove", "Halcyon"]

SEGMENTS = ["Consumer", "Corporate", "Home Office"]

# City -> region, the geography customers and stores live in.
GEOGRAPHY: dict[str, str] = {
    "Northgate": "North",
    "Ashford": "North",
    "Rivermouth": "North",
    "Southbank": "South",
    "Kingsley": "South",
    "Fairlight": "South",
    "Westcliff": "West",
    "Portvale": "West",
    "Harlow": "West",
}
CITIES = list(GEOGRAPHY)

FIRST_NAMES = [
    "Alex", "Bianca", "Cornel", "Dana", "Erik", "Farida", "Goran", "Hedda",
    "Ivo", "Jonas", "Kira", "Lena", "Milo", "Nadia", "Oskar", "Petra",
    "Quinn", "Rasa", "Sven", "Tomas", "Ula", "Viktor", "Wanda", "Yara", "Zane",
]
LAST_NAMES = [
    "Adler", "Brandt", "Calder", "Draper", "Engel", "Falk", "Grimm", "Holt",
    "Iversen", "Jansen", "Kron", "Lund", "Mayer", "Novak", "Ohlsson", "Pahl",
    "Quist", "Roth", "Salo", "Thorne", "Ulrich", "Voss", "Wenger", "Ziegler",
]


@dataclass
class Dataset:
    """Container for one deterministic build of the synthetic warehouse."""

    products: list[dict] = field(default_factory=list)
    stores: list[dict] = field(default_factory=list)
    customer_snapshots: list[tuple[dt.date, list[dict]]] = field(default_factory=list)
    sales: list[dict] = field(default_factory=list)


def _make_products(rng: random.Random) -> list[dict]:
    products: list[dict] = []
    category_cycle = list(CATEGORIES)
    for i in range(N_PRODUCTS):
        category = category_cycle[i % len(category_cycle)]
        subcategory = rng.choice(CATEGORIES[category])
        brand = rng.choice(BRANDS)
        low, high = PRICE_BANDS[category]
        unit_price = round(rng.uniform(low, high), 2)
        products.append(
            {
                "product_id": 1000 + i,
                "product_name": f"{brand} {subcategory[:-1] if subcategory.endswith('s') else subcategory} {100 + i}",
                "category": category,
                "subcategory": subcategory,
                "brand": brand,
                "unit_price": unit_price,
            }
        )
    return products


def _make_stores() -> list[dict]:
    # A fixed, hand-laid store footprint (one or two per city) so the geography
    # of a conformed store/region dimension is stable across rebuilds.
    layout = [
        ("Northgate", "Northgate Central"),
        ("Ashford", "Ashford Retail Park"),
        ("Rivermouth", "Rivermouth Quay"),
        ("Southbank", "Southbank Plaza"),
        ("Kingsley", "Kingsley High Street"),
        ("Fairlight", "Fairlight Mall"),
        ("Westcliff", "Westcliff Marina"),
        ("Portvale", "Portvale Gardens"),
    ]
    stores: list[dict] = []
    for i, (city, name) in enumerate(layout):
        stores.append(
            {
                "store_id": 10 + i,
                "store_name": name,
                "city": city,
                "region": GEOGRAPHY[city],
                "country": "Synthetica",
            }
        )
    return stores


def _make_customer_snapshots(rng: random.Random) -> list[tuple[dt.date, list[dict]]]:
    """Emit two source extracts of the customer master, six months apart.

    Snapshot 1 is the initial state. In snapshot 2 a ``CHURN_FRACTION`` slice of
    customers have changed a tracked attribute (segment and/or city). Everyone
    else is byte-identical, which lets the SCD-2 loader prove it only versions
    real changes and is idempotent on the rest.
    """

    base: list[dict] = []
    for i in range(N_CUSTOMERS):
        city = rng.choice(CITIES)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        base.append(
            {
                "customer_id": 5000 + i,
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}{i}@example.test",
                "segment": rng.choice(SEGMENTS),
                "city": city,
                "region": GEOGRAPHY[city],
            }
        )

    snapshot_1 = [dict(row) for row in base]

    # Build snapshot 2 by mutating a deterministic subset.
    changed_ids = set(rng.sample([c["customer_id"] for c in base], k=int(N_CUSTOMERS * CHURN_FRACTION)))
    snapshot_2: list[dict] = []
    for row in base:
        new_row = dict(row)
        if row["customer_id"] in changed_ids:
            if rng.random() < 0.6:
                # Segment change (e.g. a consumer becomes a corporate account).
                choices = [s for s in SEGMENTS if s != row["segment"]]
                new_row["segment"] = rng.choice(choices)
            if rng.random() < 0.6:
                # Relocation to a different city (and therefore possibly region).
                choices = [c for c in CITIES if c != row["city"]]
                new_city = rng.choice(choices)
                new_row["city"] = new_city
                new_row["region"] = GEOGRAPHY[new_city]
        snapshot_2.append(new_row)

    return [(SNAPSHOT_1, snapshot_1), (SNAPSHOT_2, snapshot_2)]


def _random_date(rng: random.Random, start: dt.date, end: dt.date) -> dt.date:
    span = (end - start).days
    return start + dt.timedelta(days=rng.randint(0, span))


def _make_sales(rng: random.Random, products: list[dict], stores: list[dict]) -> list[dict]:
    sales: list[dict] = []
    customer_ids = [5000 + i for i in range(N_CUSTOMERS)]
    for order_seq in range(N_SALES):
        product = rng.choice(products)
        store = rng.choice(stores)
        customer_id = rng.choice(customer_ids)
        order_date = _random_date(rng, SALES_START, SALES_END)
        quantity = rng.randint(1, 5)
        # A small, occasional line-level discount (0, 5, 10 or 15 %).
        discount_pct = rng.choice([0.0, 0.0, 0.0, 0.05, 0.10, 0.15])
        unit_price = product["unit_price"]
        gross = round(unit_price * quantity, 2)
        net = round(gross * (1 - discount_pct), 2)
        sales.append(
            {
                "order_id": 900000 + order_seq,
                "order_date": order_date,
                "product_id": product["product_id"],
                "store_id": store["store_id"],
                "customer_id": customer_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_pct": discount_pct,
                "gross_amount": gross,
                "net_amount": net,
            }
        )
    return sales


def generate(seed: int = SEED) -> Dataset:
    """Build one deterministic synthetic dataset."""

    rng = random.Random(seed)
    products = _make_products(rng)
    stores = _make_stores()
    customer_snapshots = _make_customer_snapshots(rng)
    sales = _make_sales(rng, products, stores)
    return Dataset(
        products=products,
        stores=stores,
        customer_snapshots=customer_snapshots,
        sales=sales,
    )
