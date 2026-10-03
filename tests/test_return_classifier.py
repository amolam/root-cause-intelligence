from types import SimpleNamespace

import pytest

import app.ai.classifier as classifier_module
from app.ai.classifier import ClassificationResult, ReturnClassificationService, requires_human_review


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


def test_low_confidence_specific_final_result_does_not_require_review():
    light = FakeClassifier("light", result(confidence=0.4))
    heavy = FakeClassifier("heavy", result(confidence=0.4))
    session = FakeSession()
    record = SimpleNamespace(return_id="R5", sku_id="S5", return_reason="Quality", return_reason_text="Fabric is rough")

    outcome = ReturnClassificationService(light, heavy).classify(session, record)

    assert outcome.result.confidence_score == 0.4
    assert outcome.human_review_status == "NOT_REQUIRED"
    assert session.rows[0].human_review_status == "NOT_REQUIRED"
    assert not requires_human_review(outcome.result)


def test_single_classifier_mode_does_not_escalate_or_call_a_second_model():
    jev = FakeClassifier("jev", result(confidence=0.2))

    prediction = classifier_module.route_prediction(jev, None, reason="Other", text="I changed my mind")

    assert jev.calls == 1
    assert prediction.model_name == "jev"
    assert prediction.escalated is False


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
    assert requires_human_review(outcome.result)


def test_changed_mind_taxonomy_is_valid_and_not_other():
    changed_mind = result(category="CUSTOMER_PREFERENCE", subcategory="CHANGED_MIND")

    assert changed_mind.predicted_category == "CUSTOMER_PREFERENCE"
    assert changed_mind.predicted_subcategory == "CHANGED_MIND"
    assert not requires_human_review(changed_mind)


def test_invalid_category_subcategory_pair_is_rejected():
    with pytest.raises(ValueError, match="not valid"):
        result(category="FIT", subcategory="STITCHING")


def test_openrouter_schema_accepts_only_known_taxonomy_pairs():
    output = classifier_module.OpenRouterClassificationOutput(
        predicted_label="QUALITY__ZIPPER",
        confidence_score=0.9,
        sentiment="negative",
        evidence_text="zip broke",
    )

    mapped = classifier_module._map_openrouter_output(output)

    assert mapped.predicted_category == "QUALITY"
    assert mapped.predicted_subcategory == "ZIPPER"
    changed_mind = classifier_module.OpenRouterClassificationOutput(
        predicted_label="CUSTOMER_PREFERENCE__CHANGED_MIND",
        confidence_score=0.9,
        sentiment="neutral",
        evidence_text="changed my mind",
    )
    assert classifier_module._map_openrouter_output(changed_mind).predicted_category == "CUSTOMER_PREFERENCE"
    with pytest.raises(ValueError):
        classifier_module.OpenRouterClassificationOutput(
            predicted_label="FIT__STITCHING",
            confidence_score=0.9,
            sentiment="negative",
            evidence_text="zip broke",
        )


def test_jev_classifier_maps_choice_and_confidence(monkeypatch):
    request_data = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "answers": {
                    "return_classification": {
                        "choice": "QUALITY__ZIPPER",
                        "confidence": 0.86,
                        "probabilities": {"QUALITY__ZIPPER": 0.93},
                    },
                    "sentiment": {"choice": "negative"},
                }
            }

    def fake_post(url, **kwargs):
        request_data["url"] = url
        request_data.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(classifier_module.requests, "post", fake_post)
    jev = classifier_module.create_jev_classifier("typesafe/jev-1.13", "test-key")
    prior = result(confidence=0.4)

    prediction = jev.classify(reason="Other", text="The zip broke", prior_result=prior)

    assert request_data["url"] == "https://openrouter.ai/api/alpha/decisions"
    assert request_data["json"]["model"] == "typesafe/jev-1.13"
    assert request_data["json"]["state"]["first_pass_prediction"]["predicted_category"] == "FIT"
    assert prediction.predicted_category == "QUALITY"
    assert prediction.predicted_subcategory == "ZIPPER"
    assert prediction.confidence_score == 0.86
    assert prediction.sentiment == "negative"
    assert prediction.extracted_issue is None
    assert prediction.evidence_text == ""


def test_second_stage_factory_selects_jev(monkeypatch):
    jev = FakeClassifier("typesafe/jev-1.13", result())
    requested = {}

    def fake_create_jev(model_name, api_key):
        requested["model_name"] = model_name
        requested["api_key"] = api_key
        return jev

    monkeypatch.setattr(classifier_module, "create_jev_classifier", fake_create_jev)

    selected = classifier_module.create_second_stage_classifier(
        backend="jev",
        openrouter_model="openai/gpt-4.1",
        jev_model="typesafe/jev-1.13",
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
    )

    assert selected is jev
    assert requested == {"model_name": "typesafe/jev-1.13", "api_key": "test-key"}
