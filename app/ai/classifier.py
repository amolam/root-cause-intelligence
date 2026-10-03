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


_SYSTEM_PROMPT = (
    "Classify an apparel return using only the supplied return reason and customer text.\n"
    "Return a single JSON object that strictly matches the schema below — no extra keys, no markdown fences.\n"
    "Evidence must be a short exact span from the customer text when available. "
    "Do not infer facts absent from the text. "
    "If evidence is ambiguous, choose OTHER / LOW_CONFIDENCE and set confidence_score below 0.75. "
    "Hinglish and transliterated Hindi are valid input.\n\n"
    "Schema fields (all required):\n"
    "  predicted_category   – one of: FIT, QUALITY, COLOUR, MATERIAL, PRODUCT_MISMATCH, DAMAGED, DELIVERY, OTHER\n"
    "  predicted_subcategory – must be valid for the chosen category per the taxonomy\n"
    "  confidence_score     – float 0.0–1.0\n"
    "  extracted_issue      – short exact quote from customer text, or null\n"
    "  sentiment            – NEGATIVE, NEUTRAL, or POSITIVE\n"
    "  evidence_text        – one sentence summarising the evidence\n\n"
    "Taxonomy: {taxonomy}\n\n"
    "Prior prediction (second-pass only, else 'None'): {prior_result}\n"
    "On a second pass, independently reassess; keep prior if supported, otherwise correct it. "
    "Do not treat prior confidence as evidence."
)

_HUMAN_PROMPT = "Return reason: {reason}\nCustomer text: {text}"


def create_openrouter_classifier(
    model_name: str,
    api_key: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
) -> "Classifier":
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
            ("system", _SYSTEM_PROMPT),
            ("human", _HUMAN_PROMPT),
        ])
        chain = prompt | structured

        class LangChainClassifier:
            def __init__(self):
                self.model_name = model_name
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


def create_requests_classifier(
    model_name: str,
    api_key: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
) -> "Classifier":
    """
    Raw-HTTP classifier for models that LangChain does not support (e.g. typesafe/jev-*).
    Calls the OpenRouter chat-completions endpoint directly via `requests` and parses
    the JSON response body into a ClassificationResult.
    """
    import json
    import requests as _requests

    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY is not configured. Add it to your local .env file.")

    endpoint = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    class RequestsClassifier:
        def __init__(self):
            self.model_name = model_name
            self.model_version = model_name

        def classify(
            self, *, reason: str, text: str, prior_result: ClassificationResult | None = None
        ) -> ClassificationResult:
            system_msg = _SYSTEM_PROMPT.format(
                taxonomy=str(TAXONOMY),
                prior_result=prior_result.model_dump_json() if prior_result else "None",
            )
            human_msg = _HUMAN_PROMPT.format(
                reason=reason,
                text=text or "[no free-text comment]",
            )
            payload = {
                "model": model_name,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": human_msg},
                ],
            }
            try:
                response = _requests.post(endpoint, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
            except _requests.RequestException as exc:
                raise ClassificationError(f"HTTP request to OpenRouter failed: {exc}") from exc

            body = response.json()
            raw_content = body["choices"][0]["message"]["content"]

            # Strip accidental markdown code fences some models include
            clean = raw_content.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]

            try:
                parsed = json.loads(clean)
            except json.JSONDecodeError as exc:
                raise ClassificationError(
                    f"Model returned non-JSON content: {raw_content[:200]}"
                ) from exc

            try:
                return ClassificationResult.model_validate(parsed)
            except Exception as exc:
                raise ClassificationError(
                    f"Model JSON does not match ClassificationResult schema: {exc}"
                ) from exc

    return RequestsClassifier()


# Models whose OpenRouter integration is incompatible with LangChain's structured-output path.
_REQUESTS_ONLY_PREFIXES = ("typesafe/jev",)


def create_classifier(
    model_name: str,
    api_key: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
) -> "Classifier":
    """
    Dispatcher: routes Jev (and other LangChain-incompatible models) to the
    raw-requests path and everything else to the LangChain path.
    """
    if any(model_name.startswith(p) for p in _REQUESTS_ONLY_PREFIXES):
        return create_requests_classifier(model_name, api_key, base_url)
    return create_openrouter_classifier(model_name, api_key, base_url)

