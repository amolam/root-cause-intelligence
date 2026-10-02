from app.db.base import Base
from app.db import models  # noqa: F401


EXPECTED_TABLES = {
    "customers", "vendors", "products", "product_size_chart", "orders", "order_items",
    "order_status_history", "returns", "reviews", "catalogue_attributes",
    "return_ai_analysis", "human_review", "sku_return_insights",
    "category_return_insights", "vendor_purchase_orders", "support_tickets",
    "app_search_events",
}


def test_all_schema_entities_are_mapped():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_return_reason_accepts_other_without_enum_constraint():
    column = Base.metadata.tables["returns"].c.return_reason
    assert column.nullable is False
    assert not column.constraints


def test_analysis_uses_documented_uuid_and_category_insight_json():
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    assert isinstance(Base.metadata.tables["return_ai_analysis"].c.analysis_id.type, UUID)
    assert isinstance(Base.metadata.tables["category_return_insights"].c.top_problem_skus.type, JSONB)
