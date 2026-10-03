from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import app.api as api_module


class FakeSession:
    def __init__(self, record=None):
        self.record = record

    def get(self, model, key):
        return self.record

    def scalar(self, statement):
        return None

    def rollback(self):
        pass


class BatchSession(FakeSession):
    def __init__(self, records, remaining):
        super().__init__()
        self.records = records
        self.remaining = remaining

    def scalars(self, statement):
        return SimpleNamespace(all=lambda: self.records)

    def scalar(self, statement):
        return self.remaining


class ResetSession(FakeSession):
    def __init__(self):
        super().__init__()
        self.executions = 0
        self.commits = 0

    def execute(self, statement):
        self.executions += 1
        if self.executions == 1:
            return SimpleNamespace(one=lambda: (
                datetime(2025, 1, 15, tzinfo=timezone.utc),
                datetime(2026, 9, 13, tzinfo=timezone.utc),
            ))
        return SimpleNamespace(rowcount=1)

    def commit(self):
        self.commits += 1


class AnalyticsSession:
    def __init__(self):
        self.scalar_queries = []
        self.queries = []
        self.results = iter([
            [("FIT", "SIZE_MISMATCH", 2), ("QUALITY", "FABRIC_QUALITY", 1)],
            [("V1", "Vendor A", 3, 4, 1)],
            [("V1", 20, 100)],
            [("SKU1", "Everyday Kurti", 3, 4, 1)],
            [("SKU1", 20, 100)],
            [("SKU1", "FIT", "SIZE_MISMATCH", 2), ("SKU1", "QUALITY", "FABRIC_QUALITY", 1)],
        ])

    def scalar(self, statement):
        self.scalar_queries.append(statement)
        return 5

    def execute(self, statement):
        self.queries.append(statement)
        return SimpleNamespace(all=lambda: next(self.results))


def client_with_session(session):
    api_module.app.dependency_overrides[api_module.get_db] = lambda: session
    return TestClient(api_module.app)


def test_health_endpoint_is_visible():
    client = TestClient(api_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_summary_distinguishes_human_reviewed_from_analysed():
    values = iter([100, 20, 85, 12, 9, 120])
    statements = []
    session = SimpleNamespace(scalar=lambda statement: (statements.append(statement), next(values))[1])

    summary = api_module.dashboard_summary(db=session)

    assert summary["analysed_returns"] == 85
    assert summary["unanalysed_returns"] == 15
    assert summary["pending_human_reviews"] == 12
    assert summary["human_reviewed_returns"] == 9
    assert sum("row_number() over" in str(statement).lower() for statement in statements) == 2


def test_pending_review_queue_filters_to_latest_analysis():
    statements = []
    session = SimpleNamespace(
        execute=lambda statement: (statements.append(statement), SimpleNamespace(all=lambda: []))[1]
    )

    assert api_module.pending_reviews(limit=50, db=session) == []

    query = str(statements[0]).lower()
    assert "row_number() over" in query
    assert "row_num = :row_num_1" in query


def test_dashboard_analytics_reports_other_coverage_vendor_rate_and_sku_drivers():
    session = AnalyticsSession()

    result = api_module.dashboard_analytics(
        start=date(2025, 1, 1), end=date(2025, 12, 31), db=session
    )

    assert result["source_other"] == {
        "total_returns": 5,
        "ai_classified_returns": 3,
        "ai_unclassified_returns": 2,
        "ai_prediction_coverage": 0.6,
        "category_mix": [
            {"category": "FIT", "return_count": 2, "share": 2 / 3},
            {"category": "QUALITY", "return_count": 1, "share": 1 / 3},
        ],
        "breakdown": [
            {"category": "FIT", "subcategory": "SIZE_MISMATCH", "return_count": 2, "share": 2 / 3},
            {"category": "QUALITY", "subcategory": "FABRIC_QUALITY", "return_count": 1, "share": 1 / 3},
        ],
    }
    vendor = result["vendors"]["by_volume"][0]
    assert vendor["return_events"] == 3
    assert vendor["returned_units"] == 4
    assert vendor["sold_units"] == 100
    assert vendor["unit_return_rate"] == 0.04
    assert vendor["sku_mismatch_returns"] == 1
    assert result["vendors"]["return_mix"] == [
        {"label": "Vendor A", "return_count": 3, "returned_units": 4, "share": 1.0}
    ]
    sku = result["skus"][0]
    assert sku["return_events"] == 3
    assert sku["return_rate"] == 3 / 20
    assert sku["unclassified_returns"] == 1
    assert [issue["category"] for issue in sku["issue_breakdown"]] == ["FIT", "QUALITY"]
    assert result["ai_classified_returns"] == 3
    assert result["ai_issue_category_mix"] == [
        {"category": "FIT", "return_count": 2, "share": 2 / 3},
        {"category": "QUALITY", "return_count": 1, "share": 1 / 3},
    ]
    ranked_query = str(session.scalar_queries[0]).lower()
    assert "row_number() over" in ranked_query
    assert "analysis_id desc" in ranked_query
    assert all("human_label" not in str(statement).lower() for statement in session.queries)


def test_dashboard_analytics_rejects_reversed_date_range():
    client = client_with_session(FakeSession())

    response = client.get("/api/dashboard/analytics?start=2025-12-31&end=2025-01-01")

    assert response.status_code == 422
    api_module.app.dependency_overrides.clear()


def test_classification_provider_error_is_visible(monkeypatch):
    record = SimpleNamespace(return_id="R1", return_reason="Other", return_reason_text="unclear")
    client = client_with_session(FakeSession(record))

    class FailedService:
        def classify(self, session, item):
            raise api_module.ClassificationError("model endpoint unavailable")

    monkeypatch.setattr(api_module, "get_classifier_service", lambda: FailedService())
    response = client.post("/api/returns/R1/classify")
    assert response.status_code == 502
    assert "model endpoint unavailable" in response.json()["detail"]
    api_module.app.dependency_overrides.clear()


def test_single_classification_refreshes_monthly_insights(monkeypatch):
    record = SimpleNamespace(return_id="R1", order_id="O1", return_reason="Other", return_reason_text="unclear")
    client = client_with_session(FakeSession(record))
    refreshed = []

    class SuccessfulService:
        def classify(self, session, item):
            return SimpleNamespace(
                analysis_id="A1",
                result=SimpleNamespace(predicted_category="FIT", predicted_subcategory="TOO_SMALL",
                                       confidence_score=0.8, evidence_text="too small"),
                model_name="test",
                human_review_status="PENDING",
            )

    monkeypatch.setattr(api_module, "get_classifier_service", lambda: SuccessfulService())
    monkeypatch.setattr(api_module, "_refresh_monthly_insights_for_return", lambda session, item: refreshed.append(item.return_id))
    response = client.post("/api/returns/R1/classify")

    assert response.status_code == 200
    assert refreshed == ["R1"]
    api_module.app.dependency_overrides.clear()


def test_batch_classification_reports_partial_results_and_remaining_count(monkeypatch):
    records = [SimpleNamespace(return_id=f"R{index}") for index in range(1, 4)]
    client = client_with_session(BatchSession(records, remaining=8))

    class BatchService:
        def classify(self, session, item):
            if item.return_id == "R3":
                raise RuntimeError("provider detail must not be returned")
            return SimpleNamespace(human_review_status="PENDING" if item.return_id == "R1" else "NOT_REQUIRED")

    monkeypatch.setattr(api_module, "get_classifier_service", lambda: BatchService())
    monkeypatch.setattr(api_module, "_refresh_monthly_insights_for_return", lambda session, item: None)
    response = client.post("/api/returns/classify-batch?limit=3")

    assert response.status_code == 200
    assert response.json() == {
        "requested": 3,
        "attempted": 3,
        "classified": 2,
        "pending_review": 1,
        "not_required": 1,
        "failed": 1,
        "remaining_unclassified": 8,
        "failures": [{"return_id": "R3", "error": "RuntimeError"}],
        "insights_refreshed": True,
        "insight_refresh_failures": [],
    }
    api_module.app.dependency_overrides.clear()


def test_batch_classification_limit_cannot_exceed_five():
    client = client_with_session(BatchSession([], remaining=0))
    response = client.post("/api/returns/classify-batch?limit=6")

    assert response.status_code == 422
    api_module.app.dependency_overrides.clear()


def test_reset_classifications_clears_records_and_refreshes_insights(monkeypatch):
    client = client_with_session(ResetSession())
    monkeypatch.setattr(api_module, "_refresh_all_insights", lambda db: (12, 8))

    response = client.post("/api/admin/reset-classifications")

    assert response.status_code == 200
    assert response.json()["analyses_deleted"] == 1
    assert response.json()["human_reviews_deleted"] == 1
    assert response.json()["insights_refreshed"] is True
    api_module.app.dependency_overrides.clear()


def test_dashboard_refresh_endpoint_recalculates_all_insights(monkeypatch):
    client = client_with_session(FakeSession())
    monkeypatch.setattr(api_module, "_refresh_all_insights", lambda db: (12, 8))

    response = client.post("/api/dashboard/refresh-insights")

    assert response.status_code == 200
    assert response.json() == {"sku_rows": 12, "category_rows": 8, "refreshed": True}
    api_module.app.dependency_overrides.clear()


def test_pending_other_review_explains_high_confidence_reason():
    analysis = SimpleNamespace(
        analysis_id=uuid4(), return_id="R1", sku_id="S1", predicted_category="OTHER",
        predicted_subcategory="OTHER", confidence_score=0.95,
        evidence_text="outside supported labels",
    )
    record = SimpleNamespace(return_reason="Other", return_reason_text="unclear")
    session = SimpleNamespace(execute=lambda statement: SimpleNamespace(all=lambda: [(analysis, record)]))

    response = api_module.pending_reviews(limit=50, db=session)

    assert response[0]["review_reasons"] == ["OTHER_CATEGORY"]
    assert response[0]["confidence_score"] == 0.95


def test_category_insights_roll_up_periods_and_link_skus():
    category_rows = [
        SimpleNamespace(category="Kurti", subcategory="Straight", analysis_period=period,
                        total_orders=100, total_returns=returns, fit_return_rate=fit_rate,
                        quality_return_rate=0.02, top_fit_issue=issue)
        for period, returns, fit_rate, issue in (
            (date(2025, 1, 1), 10, 0.05, "TOO_SMALL"),
            (date(2025, 2, 1), 20, 0.1, "TOO_LARGE"),
        )
    ]
    sku_rows = []
    for period, first_returns, second_returns in (
        (date(2025, 1, 1), 5, 5),
        (date(2025, 2, 1), 15, 5),
    ):
        for sku_id, product_name, returns in (
            ("S1", "Straight Kurti A", first_returns),
            ("S2", "Straight Kurti B", second_returns),
        ):
            sku_rows.append(("Kurti", "Straight", product_name, SimpleNamespace(
                sku_id=sku_id, analysis_period=period, total_orders=50, total_returns=returns,
                fit_returns=returns // 2, quality_count=1, colour_count=0, other_count=0,
                top_issue="FIT/TOO_SMALL",
            )))
    session = SimpleNamespace(
        scalars=lambda statement: SimpleNamespace(all=lambda: category_rows),
        execute=lambda statement: SimpleNamespace(all=lambda: sku_rows),
    )
    client = client_with_session(session)

    response = client.get("/api/dashboard/category-insights?start=2025-01-01&end=2025-02-28")
    group = response.json()[0]

    assert response.status_code == 200
    assert group["total_orders"] == 200
    assert group["total_returns"] == 30
    assert group["return_rate"] == 0.15
    assert {sku["sku_id"] for sku in group["skus"]} == {"S1", "S2"}
    assert next(sku for sku in group["skus"] if sku["sku_id"] == "S1")["total_returns"] == 20
    api_module.app.dependency_overrides.clear()


def test_human_review_rejects_category_subcategory_mismatch():
    client = client_with_session(FakeSession())
    response = client.post(f"/api/reviews/{uuid4()}", json={
        "category": "FIT", "subcategory": "STITCHING", "reviewer_id": "reviewer-1"
    })
    assert response.status_code == 422
    api_module.app.dependency_overrides.clear()
