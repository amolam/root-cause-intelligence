from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.ai.classifier import create_classifier_service
from app.db.config import get_settings
from app.db.models import Return, ReturnAIAnalysis
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify or reclassify returns with the configured model")
    parser.add_argument("--return-id", help="classify one return ID; defaults to all returns without an AI analysis")
    parser.add_argument(
        "--reclassify-pending",
        action="store_true",
        help="reclassify returns whose latest AI analysis is pending human review",
    )
    parser.add_argument("--limit", type=int, default=100, help="maximum returns to classify in one run")
    args = parser.parse_args()
    if args.return_id and args.reclassify_pending:
        parser.error("--return-id and --reclassify-pending cannot be used together")
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

    with SessionLocal() as session:
        query = select(Return)
        if args.return_id:
            query = query.where(Return.return_id == args.return_id)
        elif args.reclassify_pending:
            latest_analysis = select(
                ReturnAIAnalysis.return_id.label("return_id"),
                ReturnAIAnalysis.human_review_status.label("human_review_status"),
                func.row_number().over(
                    partition_by=ReturnAIAnalysis.return_id,
                    order_by=(ReturnAIAnalysis.created_at.desc(), ReturnAIAnalysis.analysis_id.desc()),
                ).label("row_num"),
            ).subquery()
            query = query.join(latest_analysis, latest_analysis.c.return_id == Return.return_id).where(
                latest_analysis.c.row_num == 1,
                latest_analysis.c.human_review_status == "PENDING",
            )
        else:
            query = query.where(~Return.return_id.in_(select(ReturnAIAnalysis.return_id)))
        returns = session.scalars(query.order_by(Return.return_created_at).limit(args.limit)).all()
        if not returns:
            print("No matching returns found.")
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
