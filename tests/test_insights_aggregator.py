from datetime import datetime, timezone

from app.insights.aggregator import aggregate_rows, period_start


def test_aggregates_return_rates_and_category_issues_by_order_cohort():
    orders = [
        {"order_id": "O1", "sku_id": "S1", "category": "Womenswear", "subcategory": "Kurti",
         "order_created_at": datetime(2025, 2, 1, tzinfo=timezone.utc)},
        {"order_id": "O2", "sku_id": "S1", "category": "Womenswear", "subcategory": "Kurti",
         "order_created_at": datetime(2025, 2, 2, tzinfo=timezone.utc)},
    ]
    returns = [{"return_id": "R1", "sku_id": "S1", "category": "Womenswear", "subcategory": "Kurti",
                "order_created_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
                "predicted_category": "FIT", "predicted_subcategory": "FIT_UNCOMFORTABLE"}]
    sku, category = aggregate_rows(orders, returns, "month")

    assert len(sku) == len(category) == 1
    assert sku[0]["analysis_period"].isoformat() == "2025-02-01"
    assert sku[0]["total_orders"] == 2
    assert sku[0]["total_returns"] == 1
    assert sku[0]["return_rate"] == 0.5
    assert sku[0]["fit_returns"] == 1
    assert category[0]["top_fit_issue"] == "FIT_UNCOMFORTABLE"
    assert category[0]["top_problem_skus"][0]["sku_id"] == "S1"


def test_week_period_starts_on_monday():
    assert period_start(datetime(2025, 2, 5, tzinfo=timezone.utc), "week").isoformat() == "2025-02-03"
