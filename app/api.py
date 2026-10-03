from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai.classifier import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    TAXONOMY,
    ClassificationError,
    ReturnClassificationService,
    create_openrouter_classifier,
    create_second_stage_classifier,
)
from app.db.config import get_settings
from app.db.models import (
    CategoryReturnInsight,
    HumanReview,
    Order,
    Product,
    Return,
    ReturnAIAnalysis,
    SKUReturnInsight,
)
from app.db.session import SessionLocal
from app.insights.aggregator import calculate_and_save_insights

Category = Literal["FIT", "QUALITY", "COLOUR", "MATERIAL", "PRODUCT_MISMATCH", "DAMAGED", "DELIVERY", "OTHER"]


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
    light = create_openrouter_classifier(
        settings.openrouter_light_model, settings.openrouter_api_key, settings.openrouter_base_url
    )
    heavy = create_second_stage_classifier(
        backend=settings.second_stage_backend,
        openrouter_model=settings.openrouter_heavy_model,
        jev_model=settings.jev_openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    return ReturnClassificationService(light, heavy)


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
    pending_reviews = db.scalar(
        select(func.count()).select_from(ReturnAIAnalysis)
        .where(ReturnAIAnalysis.human_review_status == "PENDING")
    ) or 0
    human_reviewed = db.scalar(
        select(func.count(func.distinct(ReturnAIAnalysis.return_id)))
        .select_from(HumanReview)
        .join(ReturnAIAnalysis, HumanReview.analysis_id == ReturnAIAnalysis.analysis_id)
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


@app.get("/api/reviews/pending")
def pending_reviews(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ReturnAIAnalysis, Return)
        .join(Return, Return.return_id == ReturnAIAnalysis.return_id)
        .where(ReturnAIAnalysis.human_review_status == "PENDING")
        .order_by(ReturnAIAnalysis.created_at.desc())
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
