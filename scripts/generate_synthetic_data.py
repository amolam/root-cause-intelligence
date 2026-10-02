#!/usr/bin/env python3
"""Generate deterministic, relational Dhaga & Co. MVP CSV fixtures.

Uses only the Python standard library. Output goes to
sample_data/dhaga_synthetic_mvp by default; existing fixtures are untouched.
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261002
RETURN_COUNT = 3100
RETURN_SKU_COUNT = 70
RARE_SKU_RETURN_COUNTS = (1, 1, 1, 2, 2)
ORDERS_PER_RETURN_SKU = 140
UTC = timezone.utc
BASE_TIME = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
OUTPUT_DEFAULT = Path(__file__).resolve().parents[1] / "sample_data" / "dhaga_synthetic_mvp"

VENDOR_HEADERS = ["vendor_id", "vendor_name", "city", "lead_time_days"]
PRODUCT_HEADERS = ["sku_id", "product_name", "category", "subcategory", "price", "colour", "fabric", "size", "vendor_id", "size_chart_id", "product_created_at", "product_active", "image_url"]
CUSTOMER_HEADERS = ["customer_id", "customer_created_at", "customer_city", "customer_state", "customer_tier"]
ORDER_HEADERS = ["order_id", "customer_id", "order_created_at", "payment_mode", "order_status", "order_value", "delivery_pincode", "delivery_city", "delivery_state", "fulfilment_center", "carrier"]
ITEM_HEADERS = ["order_item_id", "order_id", "sku_id", "quantity", "unit_price", "size", "colour", "discount"]
RETURN_HEADERS = ["return_id", "order_id", "order_item_id", "sku_id", "customer_id", "return_created_at", "return_reason", "return_reason_text", "return_status", "refund_amount", "return_quantity"]
TICKET_HEADERS = ["ticket_id", "customer_id", "order_id", "created_at", "channel", "query_text", "category_tag", "resolution_status"]
PO_HEADERS = ["po_id", "vendor_id", "sku_id", "quantity_ordered", "order_date", "expected_delivery_date", "actual_delivery_date", "po_status"]
SEARCH_HEADERS = ["event_id", "customer_id", "search_timestamp", "raw_search_query", "detected_language", "occasion_intent", "results_count"]

VENDORS = [
    ("Tiruppur", "Kaveri Knitwear Works"), ("Tiruppur", "Sri Amman Apparels"),
    ("Tiruppur", "Blue Loom Garments"), ("Tiruppur", "Kongu Cotton Studio"),
    ("Tiruppur", "Nila Textiles"), ("Tiruppur", "South Weave Collective"),
    ("Jaipur", "Rangrez Craft House"), ("Jaipur", "Pink City Prints"),
    ("Jaipur", "Mewar Ethnic Wear"), ("Jaipur", "Gulabi Block Prints"),
    ("Jaipur", "Anokhi Stitchworks"), ("Jaipur", "Aravali Garments"),
]
CITIES = [
    ("Mumbai", "Maharashtra", "Tier 1", "400"), ("Delhi", "Delhi", "Tier 1", "110"),
    ("Bengaluru", "Karnataka", "Tier 1", "560"), ("Hyderabad", "Telangana", "Tier 1", "500"),
    ("Jaipur", "Rajasthan", "Tier 2", "302"), ("Coimbatore", "Tamil Nadu", "Tier 2", "641"),
    ("Lucknow", "Uttar Pradesh", "Tier 2", "226"), ("Indore", "Madhya Pradesh", "Tier 2", "452"),
    ("Surat", "Gujarat", "Tier 2", "395"), ("Nagpur", "Maharashtra", "Tier 2", "440"),
    ("Mysuru", "Karnataka", "Tier 2", "570"), ("Jodhpur", "Rajasthan", "Tier 2", "342"),
    ("Tiruppur", "Tamil Nadu", "Tier 3", "641"), ("Ajmer", "Rajasthan", "Tier 3", "305"),
    ("Udaipur", "Rajasthan", "Tier 3", "313"), ("Gwalior", "Madhya Pradesh", "Tier 3", "474"),
    ("Bareilly", "Uttar Pradesh", "Tier 3", "243"), ("Davanagere", "Karnataka", "Tier 3", "577"),
]
COLOURS = ["Navy Blue", "navy", "NAVY_BLUE", "Indigo", "mustard", "Mustard Yellow", "Sage Green", "sage", "Maroon", "maroon_red", "Black", "Ivory", "rust", "Terracotta"]
FABRICS = ["Cotton", "pure cotton", "cotn", "Rayon", "rayon blend", "Viscose", "Linen blend", "Polyester", "Chiffon", "Georgette", "modal cotton"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
PRODUCTS = [("Kurti", "Straight Kurti"), ("Kurti", "Anarkali Kurti"), ("Kurti", "A-line Kurti"), ("Dress", "Midi Dress"), ("Dress", "Maxi Dress"), ("Co-ord Set", "Printed Co-ord"), ("Top", "Everyday Top"), ("Ethnic Set", "Kurta Set"), ("Tunic", "Printed Tunic"), ("Bottom", "Palazzo")]
REASONS = ["Size/Fit", "Quality", "Colour/Appearance", "Changed Mind", "Delivery Issue"]
OTHER_COMMENTS = [
    "Bahut tight hai, size bada chahiye", "Kurti is loose", "Colour is different from picture",
    "Photo mein shade halka tha, actual zyada dark hai", "Fabric feels different than what I expected",
    "Function ke liye liya tha, ab occasion nahi hai", "The print placement looks different on mine",
    "Parcel kholne par ek button missing tha", "Mujhe dusra colour chahiye tha", "Quality utni achhi nahi lagi",
    "Length is not as shown", "Order was a gift but recipient did not like the style",
    "Kapda thoda transparent hai", "Looks different in daylight", "Not matching with my dupatta",
    "Exchange chahiye, return nahi", "Stitching at the side looks uneven", "Online photo aur real product alag lag rahe hain",
]
WISMO = [
    "Where is my order? It has not arrived yet.", "Mera order kab tak deliver hoga?", "Tracking has not updated since yesterday.",
    "Order abhi tak nahi aaya, please status batayein.", "Can you share the latest delivery update?", "Delivery agent ne call nahi kiya.",
    "My parcel is delayed. Please check.", "Order dispatch hua ya nahi?", "Expected delivery date kya hai?", "The tracking link is not working.",
]
OTHER_TICKETS = [
    ("size_quality", "The kurti runs smaller than the size chart. Can I exchange it?"),
    ("size_quality", "Fabric quality is different from the description."),
    ("size_quality", "Is this cotton or a cotton blend?"),
    ("size_quality", "Size M is loose; please help me find the right size."),
    ("size_quality", "Colour looks different from the product photos."),
    ("size_quality", "Stitching came undone after the first wash."),
    ("size_quality", "Size chart mein chest measurement confirm kar sakte ho?"),
]
SEARCHES = [
    ("mehndi function dress", "Hinglish", "wedding"), ("office wear kurti", "English", "work"),
    ("haldi ke liye yellow suit", "Hinglish", "wedding"), ("daily wear cotton kurti", "English", "everyday"),
    ("shaadi guest outfit under 1500", "Hinglish", "wedding"), ("comfortable kurta for office", "English", "work"),
    ("Navratri garba dress", "Hinglish", "festival"), ("college ke liye simple top", "Hinglish", "college"),
    ("vacation beach dress", "English", "vacation"), ("puja ke liye kurta set", "Hinglish", "festive"),
    ("plus size anarkali", "English", "wedding"), ("cotton suit garmi ke liye", "Hinglish", "everyday"),
    ("sangeet outfit", "English", "wedding"), ("eid special kurti", "Hinglish", "festive"),
    ("blue printed co ord set", "English", "everyday"), ("birthday dinner dress", "English", "party"),
    ("rakhi function wear", "Hinglish", "festive"), ("linen office kurta", "English", "work"),
]


def stamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def write_csv(folder: Path, name: str, headers: list[str], rows: list[dict[str, object]]) -> None:
    with (folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate(folder: Path) -> dict[str, list[dict[str, object]]]:
    rng = random.Random(SEED)
    folder.mkdir(parents=True, exist_ok=True)
    vendors = [{"vendor_id": f"VEND-{i:03}", "vendor_name": name, "city": city, "lead_time_days": lead}
               for i, (city, name, lead) in enumerate([(c, n, rng.randint(8, 24)) for c, n in VENDORS], 1)]
    products = []
    for i in range(1, 501):
        category, subcategory = PRODUCTS[(i - 1) % len(PRODUCTS)]
        vendor_id = f"VEND-{rng.randint(1, 12):03}"
        products.append({"sku_id": f"SKU-{i:04}", "product_name": f"{rng.choice(['Everyday', 'Jaipur Print', 'Indigo', 'Festive', 'Soft Cotton', 'Printed'])} {subcategory} {i:03}",
                         "category": category, "subcategory": subcategory,
                         "price": f"{399 if i == 1 else 1499 if i == 2 else rng.randint(399, 1499)}.00", "colour": rng.choice(COLOURS), "fabric": rng.choice(FABRICS),
                         "size": rng.choice(SIZES), "vendor_id": vendor_id, "size_chart_id": f"CHART-{vendor_id[-3:]}",
                         "product_created_at": stamp(BASE_TIME - timedelta(days=rng.randint(10, 800))),
                         "product_active": "true", "image_url": ""})
    customers = []
    tier23 = [city for city in CITIES if city[2] in ("Tier 2", "Tier 3")]
    tier1 = [city for city in CITIES if city[2] == "Tier 1"]
    for i in range(1, 1001):
        city, state, tier, _ = rng.choice(tier23 if i <= 640 else tier1)
        customers.append({"customer_id": f"CUST-{i:04}", "customer_created_at": stamp(BASE_TIME - timedelta(days=rng.randint(1, 1000))),
                          "customer_city": city, "customer_state": state, "customer_tier": tier})
    return_products = rng.sample(products, RETURN_SKU_COUNT)
    orders, items = [], []
    orders_by_sku: dict[str, list[tuple[int, dict[str, object], dict[str, object]]]] = {}
    orders_by_customer: dict[str, list[dict[str, object]]] = {}
    for i in range(1, 10001):
        customer = rng.choice(customers)
        if i <= RETURN_SKU_COUNT * ORDERS_PER_RETURN_SKU:
            product = return_products[(i - 1) % RETURN_SKU_COUNT]
        else:
            product = rng.choice(products)
        cityrow = next(c for c in CITIES if c[0] == customer["customer_city"])
        created = BASE_TIME + timedelta(days=rng.randint(0, 620), minutes=rng.randint(0, 1439))
        order_id, item_id = f"ORD-{i:05}", f"ITEM-{i:05}"
        size = rng.choice(SIZES)
        orders.append({"order_id": order_id, "customer_id": customer["customer_id"], "order_created_at": stamp(created),
                       "payment_mode": "Cash on Delivery (COD)" if i <= 6100 else "Prepaid", "order_status": "Delivered",
                       "order_value": product["price"], "delivery_pincode": cityrow[3] + f"{rng.randint(1, 999):03}",
                       "delivery_city": customer["customer_city"], "delivery_state": customer["customer_state"],
                       "fulfilment_center": rng.choice(["Jaipur FC", "Tiruppur FC", "Bhiwandi FC"]), "carrier": rng.choice(["Delhivery", "Blue Dart", "Ecom Express", "Xpressbees"])})
        orders_by_customer.setdefault(str(customer["customer_id"]), []).append(orders[-1])
        items.append({"order_item_id": item_id, "order_id": order_id, "sku_id": product["sku_id"], "quantity": 1,
                      "unit_price": product["price"], "size": size, "colour": product["colour"], "discount": "0.00"})
        orders_by_sku.setdefault(str(product["sku_id"]), []).append((i, orders[-1], items[-1]))
    return_skus = [str(product["sku_id"]) for product in return_products]
    return_counts = dict(zip(return_skus[:len(RARE_SKU_RETURN_COUNTS)], RARE_SKU_RETURN_COUNTS))
    remaining_skus = return_skus[len(RARE_SKU_RETURN_COUNTS):]
    common_return_count, extra_return_skus = divmod(RETURN_COUNT - sum(RARE_SKU_RETURN_COUNTS), len(remaining_skus))
    return_counts.update({sku_id: common_return_count for sku_id in remaining_skus})
    for sku_id in rng.sample(remaining_skus, extra_return_skus):
        return_counts[sku_id] += 1
    selected_returns = [entry for sku_id, count in return_counts.items()
                        for entry in rng.sample(orders_by_sku[sku_id], count)]
    selected_returns.sort(key=lambda entry: entry[0])
    returns = []
    for return_index, (i, order, item) in enumerate(selected_returns):
        created = datetime.fromisoformat(order["order_created_at"]) + timedelta(days=rng.randint(3, 25))
        is_other = return_index < 1364
        returns.append({"return_id": f"RET-{i:05}", "order_id": order["order_id"], "order_item_id": item["order_item_id"],
                        "sku_id": item["sku_id"], "customer_id": order["customer_id"], "return_created_at": stamp(created),
                        "return_reason": "Other" if is_other else rng.choice(REASONS),
                        "return_reason_text": rng.choice(OTHER_COMMENTS) if is_other else "",
                        "return_status": rng.choice(["Refunded", "Exchange Completed", "Refunded"]),
                        "refund_amount": item["unit_price"] if is_other or rng.random() > 0.1 else "", "return_quantity": 1})
    tickets = []
    for i in range(1, 1001):
        customer = rng.choice(customers)
        order = rng.choice(orders_by_customer[customer["customer_id"]]) if i % 10 else None
        is_wismo = i <= 580
        tag, query = ("wismo", rng.choice(WISMO)) if is_wismo else rng.choice(OTHER_TICKETS)
        tickets.append({"ticket_id": f"TICKET-{i:04}", "customer_id": customer["customer_id"],
                        "order_id": order["order_id"] if order else "",
                        "created_at": stamp(BASE_TIME + timedelta(days=rng.randint(0, 620), minutes=rng.randint(0, 1439))),
                        "channel": rng.choice(["email", "chat", "phone", "whatsapp"]), "query_text": query,
                        "category_tag": tag, "resolution_status": rng.choice(["Resolved", "Open", "Pending Customer"])})
    pos = []
    for i in range(1, 51):
        product = rng.choice(products)
        vendor_id = product["vendor_id"]
        vendor = vendors[int(vendor_id[-3:]) - 1]
        ordered = BASE_TIME + timedelta(days=rng.randint(0, 620))
        lead = vendor["lead_time_days"]
        delay = rng.choice([-2, -1, 0, 1, 3, 7])
        actual = ordered + timedelta(days=max(2, lead + delay)) if i % 7 else None
        pos.append({"po_id": f"PO-{i:03}", "vendor_id": vendor_id, "sku_id": product["sku_id"],
                    "quantity_ordered": rng.randint(20, 400), "order_date": stamp(ordered),
                    "expected_delivery_date": stamp(ordered + timedelta(days=lead)),
                    "actual_delivery_date": stamp(actual) if actual else "", "po_status": "Fulfilled" if actual else "In Transit"})
    searches = []
    for i in range(1, 2001):
        query, language, occasion = rng.choice(SEARCHES)
        customer = rng.choice(customers)
        searches.append({"event_id": f"SEARCH-{i:05}", "customer_id": customer["customer_id"],
                         "search_timestamp": stamp(BASE_TIME + timedelta(days=rng.randint(0, 620), minutes=rng.randint(0, 1439))),
                         "raw_search_query": query, "detected_language": language, "occasion_intent": occasion,
                         "results_count": rng.randint(0, 48)})
    datasets = {"vendors": (VENDOR_HEADERS, vendors), "products": (PRODUCT_HEADERS, products),
                "customers": (CUSTOMER_HEADERS, customers), "orders": (ORDER_HEADERS, orders),
                "order_items": (ITEM_HEADERS, items), "returns": (RETURN_HEADERS, returns),
                "support_tickets": (TICKET_HEADERS, tickets), "vendor_purchase_orders": (PO_HEADERS, pos),
                "app_search_events": (SEARCH_HEADERS, searches)}
    for name, (headers, rows) in datasets.items():
        write_csv(folder, name, headers, rows)
    write_data_dictionary(folder, datasets)
    return {name: rows for name, (_, rows) in datasets.items()}


def write_data_dictionary(folder: Path, datasets: dict[str, tuple[list[str], list[dict[str, object]]]]) -> None:
    schema_descriptions = {
        "vendors": "Vendor master; `vendor_id` primary key. Exactly 12 vendors, six each in Tiruppur and Jaipur.",
        "products": "SKU master; `sku_id` primary key; `vendor_id` references vendors. Messy colour/fabric text is deliberate.",
        "customers": "Customer master; `customer_id` primary key. 640/1,000 are tier 2 or tier 3.",
        "orders": "Order headers; `order_id` primary key; `customer_id` references customers. One product line per order in this fixture.",
        "order_items": "Order lines; `order_item_id` primary key; `order_id` references orders and `sku_id` references products.",
        "returns": "Return records; `return_id` primary key; customer, order, item, and SKU keys match their parent rows. 3,100 returns; 1,364 have reason `Other`.",
        "support_tickets": "Support tickets; `ticket_id` primary key; customer and optional order keys reference their parent rows. 580/1,000 tagged `wismo`.",
        "vendor_purchase_orders": "PO lines; `po_id` primary key; vendor and SKU both match the product's vendor relationship. 50 rows.",
        "app_search_events": "Search events; `event_id` primary key; `customer_id` references customers. 2,000 rows.",
    }
    with (folder / "README.md").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# Dhaga & Co. synthetic MVP data\n\n")
        stream.write("Deterministic, entirely fictional fixtures generated with seed `20261002`. These are suitable for local/staging demos; they are not customer records. CSV columns follow `app/db/models.py`, and `order_items.csv` is included to satisfy the returns-to-order-item foreign key. Re-run `python scripts/generate_synthetic_data.py` from the repository root to regenerate.\n\n")
        stream.write("## Volumes and exact proportions\n\n| Dataset | Rows | Constraint |\n|---|---:|---|\n")
        stream.write("| Vendors | 12 | 6 Tiruppur, 6 Jaipur |\n| Products | 500 | INR 399–1,499 inclusive |\n| Customers | 1,000 | 640 tier 2/3 (64%) |\n| Orders | 10,000 | 6,100 COD (61%), 3,900 prepaid (39%) |\n| Order items | 10,000 | One line per order for straightforward return linkage |\n| Returns | 3,100 | 31% of orders; 1,364 `Other` (44%) |\n| Support tickets | 1,000 | 580 WISMO (58%), 420 sizing/quality |\n| Vendor purchase orders | 50 | Lead times vary by vendor |\n| App search events | 2,000 | Hinglish and occasion searches |\n\n")
        stream.write("## Loading order\n\nRun these commands from the repository root after applying the Alembic migrations. The order respects the database foreign keys:\n\n```powershell\n")
        for dataset in ("vendors", "customers", "products", "orders", "order_items", "returns", "vendor_purchase_orders", "support_tickets", "app_search_events"):
            stream.write(f"python -m app.ingestion.cli load {dataset} sample_data/dhaga_synthetic_mvp/{dataset}.csv\n")
        stream.write("```\n\n")
        stream.write("## Schemas and sample CSV blocks\n\n")
        for name, (headers, rows) in datasets.items():
            stream.write(f"### `{name}.csv`\n\n{schema_descriptions[name]}\n\n")
            stream.write("Fields: " + ", ".join(f"`{field}`" for field in headers) + ".\n\n")
            import io
            sample = io.StringIO(newline="")
            writer = csv.DictWriter(sample, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows[:2])
            stream.write("```csv\n" + sample.getvalue().rstrip() + "\n```\n\n")


def validate(datasets: dict[str, list[dict[str, object]]]) -> None:
    """Fail generation loudly if volumes, exact ratios, or FK links drift."""
    vendors, products = datasets["vendors"], datasets["products"]
    customers, orders = datasets["customers"], datasets["orders"]
    items, returns = datasets["order_items"], datasets["returns"]
    tickets, pos, searches = (datasets[k] for k in ("support_tickets", "vendor_purchase_orders", "app_search_events"))
    expected = {"vendors": 12, "products": 500, "customers": 1000, "orders": 10000,
                "order_items": 10000, "returns": 3100, "support_tickets": 1000,
                "vendor_purchase_orders": 50, "app_search_events": 2000}
    assert {name: len(rows) for name, rows in datasets.items()} == expected
    assert sum(row["city"] == "Tiruppur" for row in vendors) == 6
    assert sum(row["city"] == "Jaipur" for row in vendors) == 6
    assert all(399 <= float(row["price"]) <= 1499 for row in products)
    assert {float(row["price"]) for row in products} >= {399.0, 1499.0}
    assert sum(row["customer_tier"] in {"Tier 2", "Tier 3"} for row in customers) == 640
    assert sum(row["payment_mode"] == "Cash on Delivery (COD)" for row in orders) == 6100
    assert sum(row["payment_mode"] == "Prepaid" for row in orders) == 3900
    assert sum(row["return_reason"] == "Other" for row in returns) == 1364
    assert len({row["return_id"] for row in returns}) == RETURN_COUNT
    returns_per_sku: dict[str, int] = {}
    for row in returns:
        sku_id = str(row["sku_id"])
        returns_per_sku[sku_id] = returns_per_sku.get(sku_id, 0) + 1
    assert len(returns_per_sku) == RETURN_SKU_COUNT
    assert sum(count <= 2 for count in returns_per_sku.values()) == len(RARE_SKU_RETURN_COUNTS)
    assert sum(20 <= count <= 70 for count in returns_per_sku.values()) == RETURN_SKU_COUNT - len(RARE_SKU_RETURN_COUNTS)
    assert sum(row["category_tag"] == "wismo" for row in tickets) == 580
    customer_ids = {row["customer_id"] for row in customers}
    vendor_ids = {row["vendor_id"] for row in vendors}
    product_by_sku = {row["sku_id"]: row for row in products}
    order_by_id = {row["order_id"]: row for row in orders}
    item_by_id = {row["order_item_id"]: row for row in items}
    assert all(row["vendor_id"] in vendor_ids for row in products)
    assert all(row["customer_id"] in customer_ids for row in orders)
    assert all(row["order_id"] in order_by_id and row["sku_id"] in product_by_sku for row in items)
    assert all(row["customer_id"] in customer_ids and row["order_id"] in order_by_id
               and row["order_item_id"] in item_by_id and row["sku_id"] in product_by_sku
               and row["customer_id"] == order_by_id[row["order_id"]]["customer_id"]
               and row["sku_id"] == item_by_id[row["order_item_id"]]["sku_id"]
               and row["order_id"] == item_by_id[row["order_item_id"]]["order_id"] for row in returns)
    assert all(row["customer_id"] in customer_ids and (not row["order_id"] or
               (row["order_id"] in order_by_id and row["customer_id"] == order_by_id[row["order_id"]]["customer_id"])) for row in tickets)
    assert all(row["vendor_id"] in vendor_ids and row["sku_id"] in product_by_sku
               and row["vendor_id"] == product_by_sku[row["sku_id"]]["vendor_id"] for row in pos)
    assert all(row["customer_id"] in customer_ids for row in searches)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="output folder (default: sample_data/dhaga_synthetic_mvp)")
    args = parser.parse_args()
    datasets = generate(args.output)
    validate(datasets)
    print(f"Generated {sum(map(len, datasets.values())):,} rows across {len(datasets)} CSV datasets in {args.output}")
    for name, rows in datasets.items():
        print(f"  {name}: {len(rows):,}")


if __name__ == "__main__":
    main()
