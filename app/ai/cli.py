from __future__ import annotations

import argparse

from sqlalchemy import select

from app.ai.classifier import ReturnClassificationService, create_classifier
from app.db.config import get_settings
from app.db.models import Return, ReturnAIAnalysis
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify unanalysed returns with the configured OpenRouter models")
    parser.add_argument("--return-id", help="classify one return ID; defaults to all returns without an AI analysis")
    parser.add_argument("--limit", type=int, default=100, help="maximum returns to classify in one run")
    args = parser.parse_args()
    settings = get_settings()
    light = create_classifier(settings.openrouter_light_model, settings.openrouter_api_key, settings.openrouter_base_url)
    heavy = create_classifier(settings.openrouter_heavy_model, settings.openrouter_api_key, settings.openrouter_base_url)
    service = ReturnClassificationService(light, heavy)

    with SessionLocal() as session:
        query = select(Return)
        if args.return_id:
            query = query.where(Return.return_id == args.return_id)
        else:
            query = query.where(~Return.return_id.in_(select(ReturnAIAnalysis.return_id)))
        returns = session.scalars(query.order_by(Return.return_created_at).limit(args.limit)).all()
        if not returns:
            print("No matching unanalysed returns found.")
            return
        failed = 0
        for item in returns:
            try:
                outcome = service.classify(session, item)
                print(f"{item.return_id}: {outcome.result.predicted_category}/{outcome.result.predicted_subcategory} "
                      f"(confidence {outcome.result.confidence_score:.2f}; model {outcome.model_name})")
            except Exception as exc:
                session.rollback()
                failed += 1
                print(f"{item.return_id}: FAILED: {exc}")
        print(f"Finished: {len(returns) - failed} classified, {failed} failed.")


if __name__ == "__main__":
    main()
