from types import SimpleNamespace

import pytest

from app.ai.classifier import ClassificationResult, ReturnClassificationService


def result(category="FIT", subcategory="TOO_SMALL", confidence=0.91):
    return ClassificationResult(
        predicted_category=category,
        predicted_subcategory=subcategory,
        confidence_score=confidence,
        extracted_issue="too tight",
        sentiment="negative",
        evidence_text="too tight",
    )


class FakeClassifier:
    def __init__(self, name, prediction):
        self.model_name = name
        self.model_version = "test"
        self.prediction = prediction
        self.calls = []

    def classify(self, *, reason, text, prior_result=None):
        self.calls.append((reason, text, prior_result))
        return self.prediction


class FakeSession:
    def __init__(self):
        self.rows = []
        self.commits = 0

    def add(self, row):
        self.rows.append(row)

    def commit(self):
        self.commits += 1


def test_confident_prediction_uses_light_model_and_saves_analysis():
    light = FakeClassifier("light", result())
    heavy = FakeClassifier("heavy", result())
    session = FakeSession()
    record = SimpleNamespace(return_id="R1", sku_id="S1", return_reason="Other", return_reason_text="Bahut tight hai")

    outcome = ReturnClassificationService(light, heavy).classify(session, record)

    assert outcome.model_name == "light"
    assert light.calls == [("Other", "Bahut tight hai", None)]
    assert not heavy.calls
    assert session.rows[0].human_review_status == "NOT_REQUIRED"
    assert session.rows[0].human_label is None
    assert session.commits == 1


def test_low_confidence_escalates_and_marks_human_review_pending():
    light = FakeClassifier("light", result(confidence=0.4))
    heavy = FakeClassifier("heavy", result(category="OTHER", subcategory="OTHER", confidence=0.52))
    session = FakeSession()
    record = SimpleNamespace(return_id="R2", sku_id="S2", return_reason="Other", return_reason_text="Not what I expected")

    outcome = ReturnClassificationService(light, heavy).classify(session, record)

    assert len(light.calls) == len(heavy.calls) == 1
    assert heavy.calls[0][2] == light.prediction
    assert outcome.model_name == "heavy"
    assert session.rows[0].human_review_status == "PENDING"


def test_confident_escalated_result_does_not_require_review():
    light = FakeClassifier("light", result(confidence=0.4))
    heavy = FakeClassifier("heavy", result(confidence=0.94))
    session = FakeSession()
    record = SimpleNamespace(return_id="R3", sku_id="S3", return_reason="Other", return_reason_text="fits well")

    outcome = ReturnClassificationService(light, heavy).classify(session, record)

    assert outcome.human_review_status == "NOT_REQUIRED"
    assert session.rows[0].human_review_status == "NOT_REQUIRED"


def test_high_confidence_other_still_requires_human_review():
    other = result(category="OTHER", subcategory="OTHER", confidence=0.95)
    light = FakeClassifier("light", other)
    heavy = FakeClassifier("heavy", other)
    session = FakeSession()
    record = SimpleNamespace(return_id="R4", sku_id="S4", return_reason="Other", return_reason_text="unclear")

    outcome = ReturnClassificationService(light, heavy).classify(session, record)

    assert outcome.result.confidence_score == 0.95
    assert outcome.human_review_status == "PENDING"
    assert session.rows[0].human_review_status == "PENDING"


def test_invalid_category_subcategory_pair_is_rejected():
    with pytest.raises(ValueError, match="not valid"):
        result(category="FIT", subcategory="STITCHING")
