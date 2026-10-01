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


def test_human_review_rejects_category_subcategory_mismatch():
    client = client_with_session(FakeSession())
    response = client.post(f"/api/reviews/{uuid4()}", json={
        "category": "FIT", "subcategory": "STITCHING", "reviewer_id": "reviewer-1"
    })
    assert response.status_code == 422
    api_module.app.dependency_overrides.clear()
