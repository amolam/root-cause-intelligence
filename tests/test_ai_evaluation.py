import csv

from app.ai.classifier import ClassificationResult
from app.ai.evaluate import evaluate


class FixtureModel:
    model_name = "fixture"
    model_version = "fixture"

    def __init__(self):
        self.inputs = []

    def classify(self, *, reason, text, prior_result=None):
        self.inputs.append((reason, text))
        return ClassificationResult(
            predicted_category="FIT",
            predicted_subcategory="TOO_SMALL",
            confidence_score=0.9,
            sentiment="negative",
            evidence_text=text,
        )


def test_eval_reports_labels_after_inference_only(tmp_path, capsys):
    path = tmp_path / "cases.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["test_id", "return_reason", "return_text", "expected_category", "expected_subcategory"])
        writer.writeheader()
        writer.writerow({"test_id": "T1", "return_reason": "Other", "return_text": "tight", "expected_category": "FIT", "expected_subcategory": "TOO_SMALL"})
    light, heavy = FixtureModel(), FixtureModel()

    metrics = evaluate(path, light, heavy)

    assert metrics["cases"] == 1
    assert metrics["category_accuracy"] == 1
    assert metrics["subcategory_accuracy"] == 1
    assert light.inputs == [("Other", "tight")]
    assert "expected_category" not in str(light.inputs)
    assert "category accuracy 1/1" in capsys.readouterr().out
