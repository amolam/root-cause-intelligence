from __future__ import annotations

import argparse
from datetime import date

from app.db.session import SessionLocal
from app.insights.aggregator import GRAINS, calculate_and_save_insights


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate deterministic SKU and category return insights")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="inclusive order-created date")
    parser.add_argument("--end", type=date.fromisoformat, required=True, help="exclusive order-created date")
    parser.add_argument("--grain", choices=sorted(GRAINS), default="month")
    args = parser.parse_args()
    with SessionLocal() as session:
        sku_count, category_count = calculate_and_save_insights(session, args.start, args.end, args.grain)
    print(f"Saved {sku_count} SKU insight rows and {category_count} category insight rows.")


if __name__ == "__main__":
    main()
