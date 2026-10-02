from datetime import date
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


def client_with_session(session):
    api_module.app.dependency_overrides[api_module.get_db] = lambda: session
    return TestClient(api_module.app)


def test_health_endpoint_is_visible():
    client = TestClient(api_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_batch_classification_reports_partial_results_and_remaining_count(monkeypatch):
    records = [SimpleNamespace(return_id=f"R{index}") for index in range(1, 4)]
    client = client_with_session(BatchSession(records, remaining=8))

    class BatchService:
        def classify(self, session, item):
            if item.return_id == "R3":
                raise RuntimeError("provider detail must not be returned")
            return SimpleNamespace(human_review_status="PENDING" if item.return_id == "R1" else "NOT_REQUIRED")

    monkeypatch.setattr(api_module, "get_classifier_service", lambda: BatchService())
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
    }
    api_module.app.dependency_overrides.clear()


def test_batch_classification_limit_cannot_exceed_five():
    client = client_with_session(BatchSession([], remaining=0))
    response = client.post("/api/returns/classify-batch?limit=6")

    assert response.status_code == 422
    api_module.app.dependency_overrides.clear()


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
