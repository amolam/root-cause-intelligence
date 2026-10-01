from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CategoryReturnInsight,
    Order,
    OrderItem,
    Product,
    Return,
    ReturnAIAnalysis,
    SKUReturnInsight,
)

GRAINS = {"day", "week", "month"}


def period_start(value: datetime, grain: str) -> date:
    day = value.date()
    if grain == "day":
        return day
    if grain == "week":
        return day.fromordinal(day.toordinal() - day.weekday())
    if grain == "month":
        return day.replace(day=1)
    raise ValueError(f"grain must be one of {sorted(GRAINS)}")


def _rate(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))


def aggregate_rows(
    order_rows: Iterable[dict[str, Any]],
    return_rows: Iterable[dict[str, Any]],
    grain: str = "month",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pure aggregation function, easy to test without a PostgreSQL service.

    Periods are based on order creation (return cohorts), with DATE values set
    to day/week/month starts. Unclassified returns still contribute to counts
    and return rates; only classified rows contribute to issue-category counts.
    """
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {sorted(GRAINS)}")
    order_rows = list(order_rows)
    return_rows = list(return_rows)

    orders: dict[tuple[str, date], set[str]] = defaultdict(set)
    sku_categories: dict[tuple[str, date], tuple[str, str]] = {}
    for row in order_rows:
        key = (row["sku_id"], period_start(row["order_created_at"], grain))
        orders[key].add(row["order_id"])
        sku_categories[key] = (row["category"], row["subcategory"])

    returned: dict[tuple[str, date], dict[str, Any]] = defaultdict(
        lambda: {"returns": set(), "labels": Counter(), "fit_issues": Counter(), "issues": Counter()}
    )
    categories: dict[tuple[str, str, date], dict[str, Any]] = defaultdict(
        lambda: {"orders": set(), "returns": set(), "fit_issues": Counter(), "quality": 0, "fit": 0}
    )
    for (sku_id, period), order_ids in orders.items():
        category, subcategory = sku_categories[(sku_id, period)]
        categories[(category, subcategory, period)]["orders"].update(order_ids)

    for row in return_rows:
        period = period_start(row["order_created_at"], grain)
        sku_id = row["sku_id"]
        category = row["category"]
        subcategory = row["subcategory"]
        key = (sku_id, period)
        sku_categories.setdefault(key, (category, subcategory))
        bucket = returned[key]
        bucket["returns"].add(row["return_id"])
        cat_bucket = categories[(category, subcategory, period)]
        cat_bucket["returns"].add(row["return_id"])

        predicted_category = row.get("predicted_category")
        predicted_subcategory = row.get("predicted_subcategory")
        if predicted_category and predicted_subcategory:
            label = (predicted_category, predicted_subcategory)
            bucket["labels"][label] += 1
            bucket["issues"][f"{predicted_category}/{predicted_subcategory}"] += 1
            if predicted_category == "FIT":
                bucket["fit_issues"][predicted_subcategory] += 1
                cat_bucket["fit"] += 1
                cat_bucket["fit_issues"][predicted_subcategory] += 1
            if predicted_category == "QUALITY":
                cat_bucket["quality"] += 1

    sku_results = []
    for key in sorted(set(orders) | set(returned)):
        sku_id, period = key
        total_orders = len(orders.get(key, set()))
        ret = returned.get(key, {"returns": set(), "labels": Counter(), "fit_issues": Counter(), "issues": Counter()})
        total_returns = len(ret["returns"])
        labels = ret["labels"]
        fit_returns = sum(n for (cat, _), n in labels.items() if cat == "FIT")
        quality_count = sum(n for (cat, _), n in labels.items() if cat == "QUALITY")
        colour_count = sum(n for (cat, _), n in labels.items() if cat == "COLOUR")
        other_count = sum(n for (cat, _), n in labels.items() if cat == "OTHER")
        top_issue = ret["issues"].most_common(1)
        sku_results.append({
            "sku_id": sku_id,
            "analysis_period": period,
            "total_orders": total_orders,
            "total_returns": total_returns,
            "return_rate": _rate(total_returns, total_orders),
            "fit_returns": fit_returns,
            "fit_return_rate": _rate(fit_returns, total_orders),
            "too_small_count": labels.get(("FIT", "TOO_SMALL"), 0),
            "too_large_count": labels.get(("FIT", "TOO_LARGE"), 0),
            "quality_count": quality_count,
            "colour_count": colour_count,
            "other_count": other_count,
            "top_issue": top_issue[0][0] if top_issue else None,
            "calculated_at": datetime.now(timezone.utc),
        })

    # Combine SKU/category buckets, counting each order once per category-period.
    category_orders: dict[tuple[str, str, date], set[str]] = defaultdict(set)
    for row in order_rows:
        period = period_start(row["order_created_at"], grain)
        category_orders[(row["category"], row["subcategory"], period)].add(row["order_id"])
    category_results = []
    for key, bucket in sorted(categories.items()):
        category, subcategory, period = key
        total_orders = len(category_orders[key])
        total_returns = len(bucket["returns"])
        top_skus = [
            {"sku_id": x["sku_id"], "return_rate": float(x["return_rate"]), "total_returns": x["total_returns"]}
            for x in sorted((r for r in sku_results
                             if sku_categories.get((r["sku_id"], period)) == (category, subcategory)
                             and r["analysis_period"] == period and r["total_returns"] > 0),
                            key=lambda r: (r["return_rate"], r["total_returns"]), reverse=True)[:5]
        ]
        category_results.append({
            "category": category,
            "subcategory": subcategory,
            "analysis_period": period,
            "total_orders": total_orders,
            "total_returns": total_returns,
            "return_rate": _rate(total_returns, total_orders),
            "fit_return_rate": _rate(bucket["fit"], total_orders),
            "quality_return_rate": _rate(bucket["quality"], total_orders),
            "top_fit_issue": bucket["fit_issues"].most_common(1)[0][0] if bucket["fit_issues"] else None,
            "top_problem_skus": top_skus,
            "calculated_at": datetime.now(timezone.utc),
        })
    return sku_results, category_results


def calculate_and_save_insights(session: Session, start: date, end: date, grain: str = "month") -> tuple[int, int]:
    """Calculate and upsert insight rows for order cohorts in [start, end)."""
    if end <= start:
        raise ValueError("end must be later than start")
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {sorted(GRAINS)}")

    order_rows = [dict(row._mapping) for row in session.execute(
        select(OrderItem.order_id, OrderItem.sku_id, Product.category, Product.subcategory, Order.order_created_at)
        .join(Order, Order.order_id == OrderItem.order_id)
        .join(Product, Product.sku_id == OrderItem.sku_id)
        .where(Order.order_created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
               Order.order_created_at < datetime.combine(end, time.min, tzinfo=timezone.utc))
    )]
    analysis = select(
        ReturnAIAnalysis.return_id.label("return_id"),
        ReturnAIAnalysis.predicted_category.label("predicted_category"),
        ReturnAIAnalysis.predicted_subcategory.label("predicted_subcategory"),
        func.row_number().over(
            partition_by=ReturnAIAnalysis.return_id,
            order_by=ReturnAIAnalysis.created_at.desc(),
        ).label("row_num"),
    ).subquery()
    return_rows = [dict(row._mapping) for row in session.execute(
        select(Return.return_id, Return.sku_id, Product.category, Product.subcategory,
               Order.order_created_at, analysis.c.predicted_category, analysis.c.predicted_subcategory)
        .join(Order, Order.order_id == Return.order_id)
        .join(Product, Product.sku_id == Return.sku_id)
        .outerjoin(analysis, and_(analysis.c.return_id == Return.return_id, analysis.c.row_num == 1))
        .where(Order.order_created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
               Order.order_created_at < datetime.combine(end, time.min, tzinfo=timezone.utc))
    )]
    sku_rows, category_rows = aggregate_rows(order_rows, return_rows, grain)
    try:
        for row in sku_rows:
            session.merge(SKUReturnInsight(**row))
        for row in category_rows:
            session.merge(CategoryReturnInsight(**row))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(sku_rows), len(category_rows)
