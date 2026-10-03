"""Offline evaluation over a labelled CSV; expected labels never enter prompts."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.ai.classifier import (
    create_classifier_service,
    requires_human_review,
    route_prediction,
)
from app.db.config import get_settings

REQUIRED_COLUMNS = {"test_id", "return_reason", "return_text", "expected_category", "expected_subcategory"}


def evaluate(path: Path, light, heavy, confidence_threshold: float = 0.75) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(f"Evaluation CSV must include: {', '.join(sorted(REQUIRED_COLUMNS))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Evaluation CSV has no test rows")

    exact = category_correct = escalated = review = labelled_subcategories = 0
    for row in rows:
        # Only these source fields are sent to the model. Expected labels are
        # read only after inference for metric calculation.
        prediction = route_prediction(
            light, heavy,
            reason=row["return_reason"],
            text=row["return_text"],
            confidence_threshold=confidence_threshold,
        )
        category_match = prediction.result.predicted_category == row["expected_category"]
        has_expected_subcategory = bool(row["expected_subcategory"].strip())
        exact_match = category_match and (
            not has_expected_subcategory or prediction.result.predicted_subcategory == row["expected_subcategory"]
        )
        category_correct += int(category_match)
        exact += int(exact_match and has_expected_subcategory)
        labelled_subcategories += int(has_expected_subcategory)
        escalated += int(prediction.escalated)
        needs_review = requires_human_review(prediction.result)
        review += int(needs_review)
        print(
        f"{row['test_id']}: expected {row['expected_category']}/{row['expected_subcategory'] or '(category only)'}; "
            f"got {prediction.result.predicted_category}/{prediction.result.predicted_subcategory} "
            f"({prediction.result.confidence_score:.2f}, {prediction.model_name}) "
            f"{'PASS' if exact_match else 'CHECK'}"
        )
    count = len(rows)
    metrics = {
        "cases": count,
        "subcategory_accuracy": exact / labelled_subcategories if labelled_subcategories else 0,
        "category_accuracy": category_correct / count,
        "escalation_rate": escalated / count,
        "human_review_rate": review / count,
    }
    print(
        f"category accuracy {category_correct}/{count} ({metrics['category_accuracy']:.1%}); "
        f"subcategory accuracy {exact}/{labelled_subcategories} ({metrics['subcategory_accuracy']:.1%}); "
        f"escalated {escalated}/{count}; pending human review {review}/{count}."
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the return classifier against labelled example cases")
    parser.add_argument("csv_path", nargs="?", type=Path, default=Path("sample_data/return_text_test_cases.csv"))
    args = parser.parse_args()
    settings = get_settings()
    service = create_classifier_service(
        mode=settings.classification_mode,
        light_model=settings.openrouter_light_model,
        heavy_model=settings.openrouter_heavy_model,
        second_stage_backend=settings.second_stage_backend,
        jev_model=settings.jev_openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    evaluate(args.csv_path, service.light, service.heavy)


if __name__ == "__main__":
    main()
