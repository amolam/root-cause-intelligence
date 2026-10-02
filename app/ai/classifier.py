from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.db.models import Return, ReturnAIAnalysis


TAXONOMY: dict[str, set[str]] = {
    "FIT": {"TOO_SMALL", "TOO_LARGE", "SIZE_MISMATCH", "LENGTH_ISSUE", "WIDTH_ISSUE", "FIT_UNCOMFORTABLE"},
    "QUALITY": {"STITCHING", "FABRIC_QUALITY", "SEAM", "PRINT", "BUTTON", "ZIPPER"},
    "COLOUR": {"COLOUR_MISMATCH", "FADED", "DIFFERENT_FROM_IMAGE"},
    "MATERIAL": {"FABRIC_DIFFERENT", "FABRIC_UNCOMFORTABLE", "FABRIC_THICKNESS"},
    "PRODUCT_MISMATCH": {"WRONG_PRODUCT", "DIFFERENT_PRODUCT"},
    "DAMAGED": {"PRODUCT_DAMAGED"},
    "DELIVERY": {"DELIVERY_RELATED"},
    "OTHER": {"OTHER", "LOW_CONFIDENCE"},
}
Category = Literal["FIT", "QUALITY", "COLOUR", "MATERIAL", "PRODUCT_MISMATCH", "DAMAGED", "DELIVERY", "OTHER"]
DEFAULT_CONFIDENCE_THRESHOLD = 0.75


class ClassificationResult(BaseModel):
    """Validated structured output matching the proposed schema taxonomy."""

    model_config = ConfigDict(extra="forbid")

    predicted_category: Category
    predicted_subcategory: str
    confidence_score: float = Field(ge=0, le=1)
    extracted_issue: str | None = None
    sentiment: str
    evidence_text: str

    @model_validator(mode="after")
    def subcategory_matches_category(self):
        if self.predicted_subcategory not in TAXONOMY[self.predicted_category]:
            raise ValueError("predicted_subcategory is not valid for predicted_category")
        return self


class ModelPrediction(BaseModel):
    analysis_id: str
    result: ClassificationResult
    model_name: str
    model_version: str
    human_review_status: str


class RoutedPrediction(BaseModel):
    result: ClassificationResult
    model_name: str
    model_version: str
    escalated: bool


class Classifier(Protocol):
    model_name: str
    model_version: str

    def classify(
        self, *, reason: str, text: str, prior_result: ClassificationResult | None = None
    ) -> ClassificationResult: ...


class ClassificationError(RuntimeError):
    """Raised when a model is unavailable or returns invalid structured data."""


def route_prediction(
    light: Classifier,
    heavy: Classifier,
    *,
    reason: str,
    text: str,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> RoutedPrediction:
    """Apply the same two-model routing/chaining policy for API and evaluation."""
    result = light.classify(reason=reason, text=text)
    model = light
    escalated = result.confidence_score < confidence_threshold or result.predicted_category == "OTHER"
    if escalated:
        result = heavy.classify(reason=reason, text=text, prior_result=result)
        model = heavy
    return RoutedPrediction(
        result=result,
        model_name=model.model_name,
        model_version=model.model_version,
        escalated=escalated,
    )


class ReturnClassificationService:
    """Route ordinary text to a light model; escalate ambiguity to a heavier model."""

    def __init__(
        self, light: Classifier, heavy: Classifier,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.light = light
        self.heavy = heavy
        self.confidence_threshold = confidence_threshold

    def classify(self, session: Session, return_record: Return) -> ModelPrediction:
        # Deliberately pass only the source reason and free text to the model.
        # No AI/human labels or future reviews are read during inference.
        reason = return_record.return_reason
        text = return_record.return_reason_text or ""
        try:
            routed = route_prediction(
                self.light, self.heavy, reason=reason, text=text,
                confidence_threshold=self.confidence_threshold,
            )
        except Exception as exc:
            raise ClassificationError(f"Classification failed for return {return_record.return_id}: {exc}") from exc
        result = routed.result
        model_name, model_version = routed.model_name, routed.model_version

        needs_review = result.confidence_score < self.confidence_threshold or result.predicted_category == "OTHER"
        analysis = ReturnAIAnalysis(
            analysis_id=uuid4(),
            return_id=return_record.return_id,
            sku_id=return_record.sku_id,
            predicted_category=result.predicted_category,
            predicted_subcategory=result.predicted_subcategory,
            confidence_score=result.confidence_score,
            extracted_issue=result.extracted_issue,
            sentiment=result.sentiment,
            evidence_text=result.evidence_text,
            model_name=model_name,
            model_version=model_version,
            created_at=datetime.now(timezone.utc),
            human_review_status="PENDING" if needs_review else "NOT_REQUIRED",
            human_label=None,
        )
        session.add(analysis)
        session.commit()
        return ModelPrediction(
            analysis_id=str(analysis.analysis_id),
            result=result,
            model_name=model_name,
            model_version=model_version,
            human_review_status=analysis.human_review_status,
        )


def create_openrouter_classifier(
    model_name: str,
    api_key: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
) -> Classifier:
    """Build a LangChain classifier against OpenRouter's OpenAI-compatible API."""
    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY is not configured. Add it to your local .env file.")
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key,
            base_url=base_url,
            extra_body={"provider": {"require_parameters": True}},
        )
        structured = llm.with_structured_output(ClassificationResult, method="json_schema")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify an apparel return using only the supplied return reason and customer text.
Return exactly one label from the provided structured schema. Evidence must be a short exact span from the customer text when available. Do not infer facts absent from the text. If evidence is ambiguous, choose OTHER / LOW_CONFIDENCE and low confidence. Hinglish and transliterated Hindi are valid input.
Taxonomy:
{taxonomy}
Prior structured prediction (empty for first pass):
{prior_result}
On a second pass, independently reassess the first prediction against the supplied text. Keep it if supported; otherwise correct it. Do not treat its confidence as evidence.
Do not use customer, product, or review information beyond the supplied fields. Never make up evidence."""),
            ("human", "Return reason: {reason}\nCustomer text: {text}"),
        ])
        chain = prompt | structured

        class LangChainClassifier:
            def __init__(self):
                self.model_name = model_name
                # Persist the configured alias; the provider does not return an
                # immutable model build ID through this integration.
                self.model_version = model_name

            def classify(
                self, *, reason: str, text: str, prior_result: ClassificationResult | None = None
            ) -> ClassificationResult:
                value = chain.invoke({
                    "reason": reason,
                    "text": text or "[no free-text comment]",
                    "taxonomy": str(TAXONOMY),
                    "prior_result": prior_result.model_dump_json() if prior_result else "None",
                })
                return value if isinstance(value, ClassificationResult) else ClassificationResult.model_validate(value)

        return LangChainClassifier()
    except ClassificationError:
        raise
    except Exception as exc:
        raise ClassificationError(f"Could not initialize OpenRouter classifier: {exc}") from exc
