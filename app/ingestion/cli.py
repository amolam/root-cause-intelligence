from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.ingestion.csv_loader import DATASETS, load_csv


SEED_ORDER = ["customers", "products", "orders", "order_items", "returns"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load Dhaga MVP CSV datasets")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("load", help="load one dataset CSV")
    one.add_argument("dataset", choices=sorted(DATASETS))
    one.add_argument("csv_path", type=Path)
    seed = commands.add_parser("seed", help="load the bundled synthetic sample datasets")
    seed.add_argument("--directory", type=Path, default=Path("sample_data"))
    args = parser.parse_args()

    files = [(args.dataset, args.csv_path)] if args.command == "load" else [
        (name, args.directory / f"{name}.csv") for name in SEED_ORDER
    ]
    with SessionLocal() as session:
        for dataset, path in files:
            result = load_csv(session, path, dataset)
            print(f"Loaded {result.rows_loaded} rows into {result.dataset} from {path}")


if __name__ == "__main__":
    main()
