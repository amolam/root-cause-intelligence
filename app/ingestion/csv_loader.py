from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, Numeric, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.db import models
from app.db.base import Base


DATASETS: dict[str, type] = {
    "customers": models.Customer,
    "products": models.Product,
    "product_size_chart": models.ProductSizeChart,
    "orders": models.Order,
    "order_items": models.OrderItem,
    "order_status_history": models.OrderStatusHistory,
    "returns": models.Return,
    "reviews": models.Review,
    "catalogue_attributes": models.CatalogueAttribute,
    "return_ai_analysis": models.ReturnAIAnalysis,
    "human_review": models.HumanReview,
    "sku_return_insights": models.SKUReturnInsight,
    "category_return_insights": models.CategoryReturnInsight,
}


@dataclass(frozen=True)
class IngestResult:
    dataset: str
    rows_loaded: int


class CSVValidationError(ValueError):
    """A CSV schema or row validation error with line-level details."""


def _parse_value(raw: str, column: Any, row_num: int) -> Any:
    value = raw.strip()
    if value == "":
        if not column.nullable:
            raise CSVValidationError(f"line {row_num}: {column.name} is required")
        return None

    kind = column.type
    try:
        if isinstance(kind, (JSON, JSONB)):
            return json.loads(value)
        if isinstance(kind, (DateTime,)):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(kind, Date):
            return date.fromisoformat(value)
        if isinstance(kind, Numeric):
            return Decimal(value)
        if isinstance(kind, Uuid):
            return UUID(value)
        if isinstance(kind, String):
            return value
        # Boolean and integer SQLAlchemy types are checked by their python_type.
        if kind.python_type is bool:
            lowered = value.lower()
            if lowered not in {"true", "false", "1", "0", "yes", "no"}:
                raise ValueError("expected true/false")
            return lowered in {"true", "1", "yes"}
        if kind.python_type is int:
            return int(value)
        return value
    except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError) as exc:
        raise CSVValidationError(f"line {row_num}: invalid {column.name} value {value!r}: {exc}") from exc


def parse_csv(path: str | Path, dataset: str) -> list[dict[str, Any]]:
    """Validate a CSV against model columns and return clean typed row mappings.

    Cleanup is intentionally limited to trimming surrounding whitespace and
    treating blank optional cells as NULL. Domain-specific normalization is not
    performed because the schema document does not define canonical mappings.
    """
    try:
        model = DATASETS[dataset]
    except KeyError as exc:
        raise CSVValidationError(f"Unknown dataset {dataset!r}; choose from {', '.join(DATASETS)}") from exc

    table = Base.metadata.tables[model.__tablename__]
    columns = {column.name: column for column in table.columns}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise CSVValidationError("CSV is empty or has no header row")
        headers = [header.strip() for header in reader.fieldnames]
        if len(headers) != len(set(headers)):
            raise CSVValidationError("CSV contains duplicate column names")
        extra = sorted(set(headers) - set(columns))
        if extra:
            raise CSVValidationError(f"Unknown columns for {dataset}: {', '.join(extra)}")
        missing_required = sorted(name for name, col in columns.items() if not col.nullable and name not in headers)
        if missing_required:
            raise CSVValidationError(f"Missing required columns for {dataset}: {', '.join(missing_required)}")

        results = []
        for row_num, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                raise CSVValidationError(f"line {row_num}: row has more values than the header")
            row = {str(key).strip(): val for key, val in raw_row.items() if key is not None}
            if not any((v or "").strip() for v in row.values()):
                continue
            clean = {}
            for name, column in columns.items():
                raw = row.get(name, "")
                clean[name] = _parse_value(raw or "", column, row_num)
            results.append(clean)
    return results


def load_csv(session: Session, path: str | Path, dataset: str) -> IngestResult:
    """Load one CSV atomically. Any validation or database error rolls back all rows."""
    model = DATASETS.get(dataset)
    if model is None:
        raise CSVValidationError(f"Unknown dataset {dataset!r}; choose from {', '.join(DATASETS)}")
    rows = parse_csv(path, dataset)
    # Use merge so reloading the same natural/composite identifiers updates the
    # existing row; the operation is still a single transaction per dataset.
    with session.begin():
        for row in rows:
            session.merge(model(**row))
    return IngestResult(dataset=dataset, rows_loaded=len(rows))
