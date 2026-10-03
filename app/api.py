from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.orm import Session

from app.ai.classifier import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    TAXONOMY,
    ClassificationError,
    ReturnClassificationService,
    create_classifier_service,
)
from app.db.config import get_settings
from app.db.models import (
    CategoryReturnInsight,
    HumanReview,
    Order,
    OrderItem,
    Product,
    Return,
    ReturnAIAnalysis,
    SKUReturnInsight,
    Vendor,
)
from app.db.session import SessionLocal
from app.insights.aggregator import calculate_and_save_insights

Category = Literal[
    "FIT", "QUALITY", "COLOUR", "MATERIAL", "PRODUCT_MISMATCH", "DAMAGED", "DELIVERY",
    "CUSTOMER_PREFERENCE", "OTHER",
]


class ReviewInput(BaseModel):
    category: Category
    subcategory: str
    reviewer_id: str = Field(min_length=1, max_length=128)
    review_comment: str | None = None

    @field_validator("reviewer_id", "subcategory")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_taxonomy(self):
        if self.subcategory not in TAXONOMY[self.category]:
            raise ValueError("subcategory is not valid for category")
        return self


def get_db():
    with SessionLocal() as session:
        yield session


def _next_month_start(value: date) -> date:
    return date(value.year + 1, 1, 1) if value.month == 12 else date(value.year, value.month + 1, 1)


def _latest_analysis_subquery():
    return select(
        ReturnAIAnalysis.analysis_id.label("analysis_id"),
        func.row_number().over(
            partition_by=ReturnAIAnalysis.return_id,
            order_by=(ReturnAIAnalysis.created_at.desc(), ReturnAIAnalysis.analysis_id.desc()),
        ).label("row_num"),
    ).subquery()


def _refresh_monthly_insights_for_return(db: Session, record: Return) -> None:
    order_created_at = db.scalar(select(Order.order_created_at).where(Order.order_id == record.order_id))
    if order_created_at is None:
        raise ValueError(f"Order {record.order_id!r} was not found")
    start = order_created_at.date().replace(day=1)
    end = _next_month_start(start)
    calculate_and_save_insights(db, start, end, "month")


def _refresh_all_insights(db: Session) -> tuple[int, int]:
    min_order, max_order = db.execute(
        select(func.min(Order.order_created_at), func.max(Order.order_created_at))
    ).one()
    if min_order is None or max_order is None:
        return 0, 0
    start = min_order.date().replace(day=1)
    end = _next_month_start(max_order.date().replace(day=1))
    return calculate_and_save_insights(db, start, end, "month")


def _review_reasons(analysis: ReturnAIAnalysis) -> list[str]:
    reasons = []
    confidence = float(analysis.confidence_score) if analysis.confidence_score is not None else 0
    if confidence < DEFAULT_CONFIDENCE_THRESHOLD:
        reasons.append("LOW_CONFIDENCE")
    if analysis.predicted_category == "OTHER":
        reasons.append("OTHER_CATEGORY")
    return reasons


@lru_cache
def get_classifier_service() -> ReturnClassificationService:
    settings = get_settings()
    return create_classifier_service(
        mode=settings.classification_mode,
        light_model=settings.openrouter_light_model,
        heavy_model=settings.openrouter_heavy_model,
        second_stage_backend=settings.second_stage_backend,
        jev_model=settings.jev_openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


app = FastAPI(
    title="Root-Cause Intelligence",
    description="MVP API for return classification, human review, and SKU/category insights.",
    version="0.1.0",
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/admin/reset-classifications")
def reset_classifications(db: Session = Depends(get_db)):
    try:
        human_reviews_deleted = db.execute(delete(HumanReview)).rowcount or 0
        analyses_deleted = db.execute(delete(ReturnAIAnalysis)).rowcount or 0
        sku_insights_deleted = db.execute(delete(SKUReturnInsight)).rowcount or 0
        category_insights_deleted = db.execute(delete(CategoryReturnInsight)).rowcount or 0
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Classification data could not be reset") from exc

    try:
        _refresh_all_insights(db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Classifications were reset, but insights could not be recalculated") from exc
    return {
        "human_reviews_deleted": human_reviews_deleted,
        "analyses_deleted": analyses_deleted,
        "sku_insights_deleted": sku_insights_deleted,
        "category_insights_deleted": category_insights_deleted,
        "insights_refreshed": True,
    }


@app.post("/api/dashboard/refresh-insights")
def refresh_dashboard_insights(db: Session = Depends(get_db)):
    try:
        sku_rows, category_rows = _refresh_all_insights(db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Dashboard insights could not be refreshed") from exc
    return {"sku_rows": sku_rows, "category_rows": category_rows, "refreshed": True}


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    total_returns = db.scalar(select(func.count()).select_from(Return)) or 0
    other_returns = db.scalar(
        select(func.count()).select_from(Return).where(func.lower(Return.return_reason) == "other")
    ) or 0
    analysed = db.scalar(select(func.count(func.distinct(ReturnAIAnalysis.return_id)))) or 0
    latest_analysis = _latest_analysis_subquery()
    pending_reviews = db.scalar(
        select(func.count()).select_from(ReturnAIAnalysis)
        .join(latest_analysis, latest_analysis.c.analysis_id == ReturnAIAnalysis.analysis_id)
        .where(latest_analysis.c.row_num == 1, ReturnAIAnalysis.human_review_status == "PENDING")
    ) or 0
    human_reviewed = db.scalar(
        select(func.count(func.distinct(ReturnAIAnalysis.return_id)))
        .select_from(HumanReview)
        .join(ReturnAIAnalysis, HumanReview.analysis_id == ReturnAIAnalysis.analysis_id)
        .join(latest_analysis, latest_analysis.c.analysis_id == ReturnAIAnalysis.analysis_id)
        .where(latest_analysis.c.row_num == 1, ReturnAIAnalysis.human_review_status == "REVIEWED")
    ) or 0
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    return {
        "total_orders": total_orders,
        "total_returns": total_returns,
        "other_returns": other_returns,
        "other_return_share": round(other_returns / total_returns, 4) if total_returns else 0,
        "analysed_returns": analysed,
        "unanalysed_returns": max(total_returns - analysed, 0),
        "pending_human_reviews": pending_reviews,
        "human_reviewed_returns": human_reviewed,
    }


@app.get("/api/dashboard/sku-insights")
def sku_insights(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(SKUReturnInsight).order_by(
        SKUReturnInsight.analysis_period.desc(), SKUReturnInsight.return_rate.desc()
    ).limit(limit)).all()
    return [{
        "sku_id": row.sku_id,
        "analysis_period": row.analysis_period,
        "total_orders": row.total_orders,
        "total_returns": row.total_returns,
        "return_rate": row.return_rate,
        "fit_returns": row.fit_returns,
        "fit_return_rate": row.fit_return_rate,
        "top_issue": row.top_issue,
        "other_count": row.other_count,
    } for row in rows]


@app.get("/api/dashboard/category-insights")
def category_insights(
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    filters = []
    if start:
        filters.append(CategoryReturnInsight.analysis_period >= start)
    if end:
        filters.append(CategoryReturnInsight.analysis_period <= end)
    category_rows = db.scalars(select(CategoryReturnInsight).where(*filters)).all()
    sku_filters = []
    if start:
        sku_filters.append(SKUReturnInsight.analysis_period >= start)
    if end:
        sku_filters.append(SKUReturnInsight.analysis_period <= end)
    sku_rows = db.execute(
        select(Product.category, Product.subcategory, Product.product_name, SKUReturnInsight)
        .join(SKUReturnInsight, SKUReturnInsight.sku_id == Product.sku_id)
        .where(SKUReturnInsight.total_returns > 0, *sku_filters)
    ).all()

    categories = {}
    for row in category_rows:
        key = (row.category, row.subcategory)
        group = categories.setdefault(key, {
            "category": row.category,
            "subcategory": row.subcategory,
            "total_orders": 0,
            "total_returns": 0,
            "fit_orders": 0.0,
            "quality_orders": 0.0,
            "top_fit_issue": None,
            "latest_period": None,
            "skus": [],
        })
        total_orders = row.total_orders or 0
        group["total_orders"] += total_orders
        group["total_returns"] += row.total_returns or 0
        group["fit_orders"] += float(row.fit_return_rate or 0) * total_orders
        group["quality_orders"] += float(row.quality_return_rate or 0) * total_orders
        if group["latest_period"] is None or row.analysis_period > group["latest_period"]:
            group["latest_period"] = row.analysis_period
            group["top_fit_issue"] = row.top_fit_issue

    skus_by_category = {}
    for category, subcategory, product_name, row in sku_rows:
        key = (category, subcategory, row.sku_id)
        group = skus_by_category.setdefault(key, {
            "sku_id": row.sku_id,
            "product_name": product_name,
            "total_orders": 0,
            "total_returns": 0,
            "fit_returns": 0,
            "quality_count": 0,
            "colour_count": 0,
            "other_count": 0,
            "top_issue": None,
            "latest_period": None,
        })
        group["total_orders"] += row.total_orders or 0
        group["total_returns"] += row.total_returns or 0
        group["fit_returns"] += row.fit_returns or 0
        group["quality_count"] += row.quality_count or 0
        group["colour_count"] += row.colour_count or 0
        group["other_count"] += row.other_count or 0
        if group["latest_period"] is None or row.analysis_period > group["latest_period"]:
            group["latest_period"] = row.analysis_period
            group["top_issue"] = row.top_issue
    for (category, subcategory, _), sku in skus_by_category.items():
        total_orders = sku["total_orders"]
        sku["return_rate"] = round(sku["total_returns"] / total_orders, 4) if total_orders else 0
        sku["small_sample"] = total_orders < 30
        categories[(category, subcategory)]["skus"].append(sku)

    results = []
    for group in categories.values():
        orders = group.pop("total_orders")
        group["total_orders"] = orders
        group["return_rate"] = round(group["total_returns"] / orders, 4) if orders else 0
        group["fit_return_rate"] = round(group.pop("fit_orders") / orders, 4) if orders else 0
        group["quality_return_rate"] = round(group.pop("quality_orders") / orders, 4) if orders else 0
        group["small_sample"] = orders < 30
        group.pop("latest_period")
        group["skus"].sort(key=lambda sku: (sku["return_rate"], sku["total_returns"]), reverse=True)
        results.append(group)
    results.sort(key=lambda row: (row["return_rate"], row["total_returns"]), reverse=True)
    return results[:limit]


@app.get("/api/dashboard/analytics")
def dashboard_analytics(
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start")

    order_filters = []
    if start:
        order_filters.append(Order.order_created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc))
    if end:
        order_filters.append(
            Order.order_created_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    ranked_analysis = select(
        ReturnAIAnalysis.return_id.label("return_id"),
        ReturnAIAnalysis.predicted_category.label("predicted_category"),
        ReturnAIAnalysis.predicted_subcategory.label("predicted_subcategory"),
        func.row_number().over(
            partition_by=ReturnAIAnalysis.return_id,
            order_by=(ReturnAIAnalysis.created_at.desc(), ReturnAIAnalysis.analysis_id.desc()),
        ).label("row_num"),
    ).subquery()
    return_facts = select(
        Return.return_id.label("return_id"),
        Return.order_id.label("order_id"),
        Return.sku_id.label("sku_id"),
        Return.return_quantity.label("return_quantity"),
        Return.return_reason.label("return_reason"),
        ranked_analysis.c.predicted_category.label("predicted_category"),
        ranked_analysis.c.predicted_subcategory.label("predicted_subcategory"),
    ).join(Order, Order.order_id == Return.order_id).outerjoin(
        ranked_analysis,
        and_(ranked_analysis.c.return_id == Return.return_id, ranked_analysis.c.row_num == 1),
    ).where(*order_filters).subquery()

    source_other = func.lower(return_facts.c.return_reason) == "other"
    source_other_total = db.scalar(
        select(func.count()).select_from(return_facts).where(source_other)
    ) or 0
    source_other_rows = db.execute(
        select(
            return_facts.c.predicted_category,
            return_facts.c.predicted_subcategory,
            func.count(func.distinct(return_facts.c.return_id)),
        ).where(
            source_other,
            return_facts.c.predicted_category.is_not(None),
            return_facts.c.predicted_subcategory.is_not(None),
        ).group_by(return_facts.c.predicted_category, return_facts.c.predicted_subcategory)
    ).all()
    source_other_classified = sum(count for _, _, count in source_other_rows)
    source_other_breakdown = [{
        "category": category,
        "subcategory": subcategory,
        "return_count": int(count),
        "share": count / source_other_classified if source_other_classified else 0,
    } for category, subcategory, count in sorted(source_other_rows, key=lambda row: (-row[2], row[0], row[1]))]
    source_other_category_counts: dict[str, int] = {}
    for category, _, count in source_other_rows:
        source_other_category_counts[category] = source_other_category_counts.get(category, 0) + count
    source_other_category_mix = [{
        "category": category,
        "return_count": count,
        "share": count / source_other_classified if source_other_classified else 0,
    } for category, count in sorted(source_other_category_counts.items(), key=lambda row: (-row[1], row[0]))]

    vendor_returns = db.execute(
        select(
            Vendor.vendor_id,
            Vendor.vendor_name,
            func.count(func.distinct(Return.return_id)),
            func.coalesce(func.sum(Return.return_quantity), 0),
            func.coalesce(func.sum(case((OrderItem.sku_id != Return.sku_id, 1), else_=0)), 0),
        ).select_from(Return)
        .join(Order, Order.order_id == Return.order_id)
        .join(OrderItem, and_(OrderItem.order_item_id == Return.order_item_id, OrderItem.order_id == Return.order_id))
        .join(Product, Product.sku_id == OrderItem.sku_id)
        .join(Vendor, Vendor.vendor_id == Product.vendor_id)
        .where(*order_filters)
        .group_by(Vendor.vendor_id, Vendor.vendor_name)
    ).all()
    vendor_sales = db.execute(
        select(
            Vendor.vendor_id,
            func.count(func.distinct(Order.order_id)),
            func.coalesce(func.sum(OrderItem.quantity), 0),
        ).select_from(OrderItem)
        .join(Order, Order.order_id == OrderItem.order_id)
        .join(Product, Product.sku_id == OrderItem.sku_id)
        .join(Vendor, Vendor.vendor_id == Product.vendor_id)
        .where(*order_filters)
        .group_by(Vendor.vendor_id)
    ).all()
    sales_by_vendor = {vendor_id: (sold_orders, sold_units) for vendor_id, sold_orders, sold_units in vendor_sales}
    vendor_metrics = []
    for vendor_id, vendor_name, return_events, returned_units, mismatch_count in vendor_returns:
        sold_orders, sold_units = sales_by_vendor.get(vendor_id, (0, 0))
        sold_units = int(sold_units)
        returned_units = int(returned_units)
        vendor_metrics.append({
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "return_events": int(return_events),
            "returned_units": returned_units,
            "sold_orders": int(sold_orders),
            "sold_units": sold_units,
            "unit_return_rate": returned_units / sold_units if sold_units else 0,
            "small_sample": sold_units < 30,
            "sku_mismatch_returns": int(mismatch_count),
        })
    vendors_by_volume = sorted(
        vendor_metrics,
        key=lambda row: (-row["returned_units"], -row["return_events"], row["vendor_name"]),
    )[:limit]
    vendors_by_rate = sorted(
        (row for row in vendor_metrics if not row["small_sample"]),
        key=lambda row: (-row["unit_return_rate"], -row["return_events"], row["vendor_name"]),
    )[:limit]
    vendor_mix_source = sorted(vendor_metrics, key=lambda row: (-row["returned_units"], row["vendor_name"]))
    vendor_return_total = sum(row["returned_units"] for row in vendor_mix_source)
    vendor_return_mix = [{
        "label": row["vendor_name"],
        "return_count": row["return_events"],
        "returned_units": row["returned_units"],
        "share": row["returned_units"] / vendor_return_total if vendor_return_total else 0,
    } for row in vendor_mix_source[:6]]
    other_vendor_units = sum(row["returned_units"] for row in vendor_mix_source[6:])
    other_vendor_returns = sum(row["return_events"] for row in vendor_mix_source[6:])
    if other_vendor_units:
        vendor_return_mix.append({
            "label": "Other vendors",
            "return_count": other_vendor_returns,
            "returned_units": other_vendor_units,
            "share": other_vendor_units / vendor_return_total if vendor_return_total else 0,
        })

    sku_return_rows = db.execute(
        select(
            return_facts.c.sku_id,
            Product.product_name,
            func.count(func.distinct(return_facts.c.return_id)),
            func.coalesce(func.sum(return_facts.c.return_quantity), 0),
            func.sum(case((and_(
                return_facts.c.predicted_category.is_not(None),
                return_facts.c.predicted_subcategory.is_not(None),
            ), 0), else_=1)),
        ).join(Product, Product.sku_id == return_facts.c.sku_id)
        .group_by(return_facts.c.sku_id, Product.product_name)
    ).all()
    sku_sales_rows = db.execute(
        select(
            OrderItem.sku_id,
            func.count(func.distinct(Order.order_id)),
            func.coalesce(func.sum(OrderItem.quantity), 0),
        ).select_from(OrderItem)
        .join(Order, Order.order_id == OrderItem.order_id)
        .where(*order_filters)
        .group_by(OrderItem.sku_id)
    ).all()
    sales_by_sku = {sku_id: (sold_orders, sold_units) for sku_id, sold_orders, sold_units in sku_sales_rows}
    sku_issue_rows = db.execute(
        select(
            return_facts.c.sku_id,
            return_facts.c.predicted_category,
            return_facts.c.predicted_subcategory,
            func.count(func.distinct(return_facts.c.return_id)),
        ).where(
            return_facts.c.predicted_category.is_not(None),
            return_facts.c.predicted_subcategory.is_not(None),
        ).group_by(
            return_facts.c.sku_id,
            return_facts.c.predicted_category,
            return_facts.c.predicted_subcategory,
        )
    ).all()
    issues_by_sku: dict[str, list[dict]] = {}
    for sku_id, category, subcategory, count in sku_issue_rows:
        issues_by_sku.setdefault(sku_id, []).append({
            "category": category,
            "subcategory": subcategory,
            "return_count": int(count),
        })
    issue_category_counts: dict[str, int] = {}
    for _, category, _, count in sku_issue_rows:
        issue_category_counts[category] = issue_category_counts.get(category, 0) + count
    ai_classified_returns = sum(issue_category_counts.values())
    issue_category_mix = [{
        "category": category,
        "return_count": count,
        "share": count / ai_classified_returns if ai_classified_returns else 0,
    } for category, count in sorted(issue_category_counts.items(), key=lambda row: (-row[1], row[0]))]

    sku_metrics = []
    for sku_id, product_name, return_events, returned_units, unclassified_count in sku_return_rows:
        sold_orders, sold_units = sales_by_sku.get(sku_id, (0, 0))
        issue_breakdown = sorted(
            issues_by_sku.get(sku_id, []),
            key=lambda row: (-row["return_count"], row["category"], row["subcategory"]),
        )
        sku_metrics.append({
            "sku_id": sku_id,
            "product_name": product_name,
            "return_events": int(return_events),
            "returned_units": int(returned_units),
            "sold_orders": int(sold_orders),
            "sold_units": int(sold_units),
            "return_rate": return_events / sold_orders if sold_orders else 0,
            "small_sample": sold_orders < 30,
            "unclassified_returns": int(unclassified_count or 0),
            "issue_breakdown": issue_breakdown,
        })
    sku_metrics.sort(key=lambda row: (-row["return_events"], -row["returned_units"], row["sku_id"]))

    return {
        "date_range": {"start": start, "end": end, "basis": "order_created_at"},
        "source_other": {
            "total_returns": int(source_other_total),
            "ai_classified_returns": int(source_other_classified),
            "ai_unclassified_returns": int(source_other_total - source_other_classified),
            "ai_prediction_coverage": source_other_classified / source_other_total if source_other_total else 0,
            "category_mix": source_other_category_mix,
            "breakdown": source_other_breakdown,
        },
        "vendors": {
            "by_volume": vendors_by_volume,
            "by_rate": vendors_by_rate,
            "return_mix": vendor_return_mix,
            "minimum_sold_units_for_rate_rank": 30,
        },
        "ai_issue_category_mix": issue_category_mix,
        "ai_classified_returns": int(ai_classified_returns),
        "skus": sku_metrics[:limit],
        "data_quality": {
            "return_order_item_sku_mismatches": sum(row["sku_mismatch_returns"] for row in vendor_metrics),
        },
    }


@app.get("/api/reviews/pending")
def pending_reviews(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    latest_analysis = _latest_analysis_subquery()
    rows = db.execute(
        select(ReturnAIAnalysis, Return)
        .join(latest_analysis, latest_analysis.c.analysis_id == ReturnAIAnalysis.analysis_id)
        .join(Return, Return.return_id == ReturnAIAnalysis.return_id)
        .where(latest_analysis.c.row_num == 1, ReturnAIAnalysis.human_review_status == "PENDING")
        .order_by(ReturnAIAnalysis.created_at.desc(), ReturnAIAnalysis.analysis_id.desc())
        .limit(limit)
    ).all()
    return [{
        "analysis_id": str(analysis.analysis_id),
        "return_id": analysis.return_id,
        "sku_id": analysis.sku_id,
        "return_reason": ret.return_reason,
        "return_reason_text": ret.return_reason_text,
        "predicted_category": analysis.predicted_category,
        "predicted_subcategory": analysis.predicted_subcategory,
        "confidence_score": analysis.confidence_score,
        "review_reasons": _review_reasons(analysis),
        "evidence_text": analysis.evidence_text,
    } for analysis, ret in rows]


@app.post("/api/returns/{return_id}/classify")
def classify_return(return_id: str, db: Session = Depends(get_db)):
    record = db.get(Return, return_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Return {return_id!r} was not found")
    existing = db.scalar(
        select(ReturnAIAnalysis).where(ReturnAIAnalysis.return_id == return_id)
        .order_by(ReturnAIAnalysis.created_at.desc()).limit(1)
    )
    if existing is not None:
        try:
            _refresh_monthly_insights_for_return(db, record)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail="Classification exists, but its monthly insights could not be refreshed") from exc
        return {
            "analysis_id": str(existing.analysis_id),
            "return_id": return_id,
            "predicted_category": existing.predicted_category,
            "predicted_subcategory": existing.predicted_subcategory,
            "confidence_score": existing.confidence_score,
            "evidence_text": existing.evidence_text,
            "model_name": existing.model_name,
            "human_review_status": existing.human_review_status,
            "already_classified": True,
        }
    try:
        prediction = get_classifier_service().classify(db, record)
    except ClassificationError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Classification could not be completed: {exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database or model service is unavailable; no result was saved") from exc
    try:
        _refresh_monthly_insights_for_return(db, record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Classification was saved, but its monthly insights could not be refreshed") from exc
    return {
        "analysis_id": prediction.analysis_id,
        "return_id": return_id,
        "predicted_category": prediction.result.predicted_category,
        "predicted_subcategory": prediction.result.predicted_subcategory,
        "confidence_score": prediction.result.confidence_score,
        "evidence_text": prediction.result.evidence_text,
        "model_name": prediction.model_name,
        "human_review_status": prediction.human_review_status,
        "already_classified": False,
    }


@app.post("/api/returns/classify-batch")
def classify_returns_batch(limit: int = Query(default=5, ge=1, le=5), db: Session = Depends(get_db)):
    unanalysed = ~Return.return_id.in_(select(ReturnAIAnalysis.return_id))
    records = db.scalars(
        select(Return).where(unanalysed).order_by(Return.return_created_at).limit(limit)
    ).all()
    counts = {"classified": 0, "pending_review": 0, "not_required": 0, "failed": 0}
    failures = []
    insight_refresh_failures = []
    if records:
        try:
            service = get_classifier_service()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Classification service is unavailable; no results were processed") from exc
        for record in records:
            try:
                outcome = service.classify(db, record)
            except Exception as exc:
                db.rollback()
                counts["failed"] += 1
                failures.append({"return_id": record.return_id, "error": type(exc).__name__})
                continue
            counts["classified"] += 1
            if outcome.human_review_status == "PENDING":
                counts["pending_review"] += 1
            else:
                counts["not_required"] += 1
            try:
                _refresh_monthly_insights_for_return(db, record)
            except Exception as exc:
                db.rollback()
                insight_refresh_failures.append({"return_id": record.return_id, "error": type(exc).__name__})
    remaining = db.scalar(select(func.count()).select_from(Return).where(unanalysed)) or 0
    return {
        "requested": limit,
        "attempted": len(records),
        **counts,
        "remaining_unclassified": remaining,
        "failures": failures,
        "insights_refreshed": not insight_refresh_failures,
        "insight_refresh_failures": insight_refresh_failures,
    }


@app.post("/api/reviews/{analysis_id}")
def submit_human_review(analysis_id: UUID, payload: ReviewInput, db: Session = Depends(get_db)):
    analysis = db.get(ReturnAIAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="AI analysis was not found")
    ai_prediction = f"{analysis.predicted_category}/{analysis.predicted_subcategory}"
    human_label = f"{payload.category}/{payload.subcategory}"
    review = HumanReview(
        review_id=uuid4(),
        analysis_id=analysis_id,
        reviewer_id=payload.reviewer_id,
        ai_prediction=ai_prediction,
        human_label=human_label,
        correct=ai_prediction == human_label,
        review_comment=payload.review_comment,
    )
    analysis.human_review_status = "REVIEWED"
    analysis.human_label = human_label
    db.add(review)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Review could not be saved; please retry") from exc
    return {"analysis_id": str(analysis_id), "human_label": human_label, "correct": review.correct}
