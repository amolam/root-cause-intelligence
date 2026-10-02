"""SQLAlchemy mappings for fields listed in the MVP schema document.

No business attributes are added here. Constraints that require identifiers or
relationships are marked as implementation assumptions in README.md.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, func,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_city: Mapped[str | None] = mapped_column(String)
    customer_state: Mapped[str | None] = mapped_column(String)
    customer_tier: Mapped[str | None] = mapped_column(String)




class Vendor(Base):
    __tablename__ = "vendors"
    vendor_id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    sku_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    subcategory: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    colour: Mapped[str] = mapped_column(String, nullable=False)
    fabric: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[str] = mapped_column(String, nullable=False)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    size_chart_id: Mapped[str | None] = mapped_column(String)
    product_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    product_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String)


class ProductSizeChart(Base):
    __tablename__ = "product_size_chart"
    __table_args__ = (UniqueConstraint("size_chart_id", "vendor_id", "size_label", name="uq_size_chart_vendor_size"),)
    size_chart_id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), primary_key=True)
    size_label: Mapped[str] = mapped_column(String, primary_key=True)
    chest_min: Mapped[Decimal | None] = mapped_column(Numeric)
    chest_max: Mapped[Decimal | None] = mapped_column(Numeric)
    waist_min: Mapped[Decimal | None] = mapped_column(Numeric)
    waist_max: Mapped[Decimal | None] = mapped_column(Numeric)
    length: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String)


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    order_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String, nullable=False)
    order_status: Mapped[str] = mapped_column(String, nullable=False)
    order_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    delivery_pincode: Mapped[str] = mapped_column(String, nullable=False)
    delivery_city: Mapped[str | None] = mapped_column(String)
    delivery_state: Mapped[str | None] = mapped_column(String)
    fulfilment_center: Mapped[str | None] = mapped_column(String)
    carrier: Mapped[str | None] = mapped_column(String)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
        ForeignKeyConstraint(["sku_id"], ["products.sku_id"]),
        UniqueConstraint("order_item_id", "order_id", name="uq_order_item_order"),
    )
    order_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    size: Mapped[str] = mapped_column(String, nullable=False)
    colour: Mapped[str] = mapped_column(String, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    status_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(String)
    carrier: Mapped[str | None] = mapped_column(String)


class Return(Base):
    __tablename__ = "returns"
    __table_args__ = (ForeignKeyConstraint(["order_item_id", "order_id"], ["order_items.order_item_id", "order_items.order_id"], name="fk_return_order_item_order"),)
    return_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    order_item_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    return_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    return_reason: Mapped[str] = mapped_column(String, nullable=False)  # "Other" is valid.
    return_reason_text: Mapped[str | None] = mapped_column(Text)
    return_status: Mapped[str] = mapped_column(String, nullable=False)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    return_quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class Review(Base):
    __tablename__ = "reviews"
    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    review_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text)
    verified_purchase: Mapped[bool | None] = mapped_column(Boolean)


class CatalogueAttribute(Base):
    __tablename__ = "catalogue_attributes"
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), primary_key=True)
    attribute_name: Mapped[str] = mapped_column(String, primary_key=True)
    attribute_value: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReturnAIAnalysis(Base):
    __tablename__ = "return_ai_analysis"
    analysis_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    return_id: Mapped[str] = mapped_column(ForeignKey("returns.return_id"), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), nullable=False, index=True)
    predicted_category: Mapped[str | None] = mapped_column(String)
    predicted_subcategory: Mapped[str | None] = mapped_column(String)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    extracted_issue: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String)
    evidence_text: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String)
    model_version: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    human_review_status: Mapped[str | None] = mapped_column(String)
    human_label: Mapped[str | None] = mapped_column(String)


class HumanReview(Base):
    __tablename__ = "human_review"
    review_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("return_ai_analysis.analysis_id"), nullable=False, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String)
    ai_prediction: Mapped[str | None] = mapped_column(String)
    human_label: Mapped[str | None] = mapped_column(String)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SKUReturnInsight(Base):
    __tablename__ = "sku_return_insights"
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), primary_key=True)
    analysis_period: Mapped[date] = mapped_column(Date, primary_key=True)
    total_orders: Mapped[int | None] = mapped_column(Integer)
    total_returns: Mapped[int | None] = mapped_column(Integer)
    return_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    fit_returns: Mapped[int | None] = mapped_column(Integer)
    fit_return_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    too_small_count: Mapped[int | None] = mapped_column(Integer)
    too_large_count: Mapped[int | None] = mapped_column(Integer)
    quality_count: Mapped[int | None] = mapped_column(Integer)
    colour_count: Mapped[int | None] = mapped_column(Integer)
    other_count: Mapped[int | None] = mapped_column(Integer)
    top_issue: Mapped[str | None] = mapped_column(String)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CategoryReturnInsight(Base):
    __tablename__ = "category_return_insights"
    __table_args__ = (UniqueConstraint("category", "subcategory", "analysis_period", name="uq_category_insight_period"),)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    subcategory: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_period: Mapped[date] = mapped_column(Date, primary_key=True)
    total_orders: Mapped[int | None] = mapped_column(Integer)
    total_returns: Mapped[int | None] = mapped_column(Integer)
    return_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    fit_return_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    quality_return_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    top_fit_issue: Mapped[str | None] = mapped_column(String)
    top_problem_skus: Mapped[dict | list | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VendorPurchaseOrder(Base):
    """One row per vendor PO / SKU, as proposed in the updated schema."""
    __tablename__ = "vendor_purchase_orders"
    __table_args__ = (
        ForeignKeyConstraint(["sku_id"], ["products.sku_id"], name="fk_vendor_po_sku"),
        CheckConstraint("quantity_ordered > 0", name="ck_vendor_po_quantity_positive"),
    )
    po_id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    po_status: Mapped[str] = mapped_column(String, nullable=False)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.order_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_tag: Mapped[str | None] = mapped_column(String)
    resolution_status: Mapped[str] = mapped_column(String, nullable=False)


class AppSearchEvent(Base):
    __tablename__ = "app_search_events"
    __table_args__ = (
        CheckConstraint("results_count IS NULL OR results_count >= 0", name="ck_app_search_results_nonnegative"),
    )
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    search_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raw_search_query: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String)
    occasion_intent: Mapped[str | None] = mapped_column(String)
    results_count: Mapped[int | None] = mapped_column(Integer)
