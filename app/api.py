from __future__ import annotations

from functools import lru_cache
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.classifier import (
    TAXONOMY,
    ClassificationError,
    ReturnClassificationService,
    create_openrouter_classifier,
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


@lru_cache
def get_classifier_service() -> ReturnClassificationService:
    settings = get_settings()
    light = create_openrouter_classifier(
        settings.openrouter_light_model, settings.openrouter_api_key, settings.openrouter_base_url
    )
    heavy = create_openrouter_classifier(
        settings.openrouter_heavy_model, settings.openrouter_api_key, settings.openrouter_base_url
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
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    return {
        "total_orders": total_orders,
        "total_returns": total_returns,
        "other_returns": other_returns,
        "other_return_share": round(other_returns / total_returns, 4) if total_returns else 0,
        "analysed_returns": analysed,
        "unanalysed_returns": max(total_returns - analysed, 0),
        "pending_human_reviews": pending_reviews,
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
def category_insights(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(CategoryReturnInsight).order_by(
        CategoryReturnInsight.analysis_period.desc(), CategoryReturnInsight.return_rate.desc()
    ).limit(limit)).all()
    return [{
        "category": row.category,
        "subcategory": row.subcategory,
        "analysis_period": row.analysis_period,
        "total_orders": row.total_orders,
        "total_returns": row.total_returns,
        "return_rate": row.return_rate,
        "fit_return_rate": row.fit_return_rate,
        "quality_return_rate": row.quality_return_rate,
        "top_fit_issue": row.top_fit_issue,
        "top_problem_skus": row.top_problem_skus,
    } for row in rows]


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
