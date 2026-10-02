"""Add vendor purchase orders, support tickets, and app search events.

Revision ID: 0004_operational_data
Revises: 0003_vendors
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0004_operational_data"
down_revision = "0003_vendors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial revision emits all current metadata for offline SQL output.
    # Keep online upgrades from older databases guarded and additive below.
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("vendor_purchase_orders"):
        op.create_table(
            "vendor_purchase_orders",
            sa.Column("po_id", sa.String(), nullable=False),
            sa.Column("vendor_id", sa.String(), nullable=False),
            sa.Column("sku_id", sa.String(), nullable=False),
            sa.Column("quantity_ordered", sa.Integer(), nullable=False),
            sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expected_delivery_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_delivery_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("po_status", sa.String(), nullable=False),
            sa.CheckConstraint("quantity_ordered > 0", name="ck_vendor_po_quantity_positive"),
            sa.ForeignKeyConstraint(["sku_id"], ["products.sku_id"], name="fk_vendor_po_sku"),
            sa.ForeignKeyConstraint(["vendor_id"], ["vendors.vendor_id"]),
            sa.PrimaryKeyConstraint("po_id"),
        )
        op.create_index("ix_vendor_purchase_orders_vendor_id", "vendor_purchase_orders", ["vendor_id"])
        op.create_index("ix_vendor_purchase_orders_sku_id", "vendor_purchase_orders", ["sku_id"])

    bind = op.get_bind()
    if not sa.inspect(bind).has_table("support_tickets"):
        op.create_table(
            "support_tickets",
            sa.Column("ticket_id", sa.String(), nullable=False),
            sa.Column("customer_id", sa.String(), nullable=False),
            sa.Column("order_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("category_tag", sa.String(), nullable=True),
            sa.Column("resolution_status", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
            sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
            sa.PrimaryKeyConstraint("ticket_id"),
        )
        op.create_index("ix_support_tickets_customer_id", "support_tickets", ["customer_id"])
        op.create_index("ix_support_tickets_order_id", "support_tickets", ["order_id"])
        op.create_index("ix_support_tickets_created_at", "support_tickets", ["created_at"])

    bind = op.get_bind()
    if not sa.inspect(bind).has_table("app_search_events"):
        op.create_table(
            "app_search_events",
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("customer_id", sa.String(), nullable=False),
            sa.Column("search_timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("raw_search_query", sa.Text(), nullable=False),
            sa.Column("detected_language", sa.String(), nullable=True),
            sa.Column("occasion_intent", sa.String(), nullable=True),
            sa.Column("results_count", sa.Integer(), nullable=True),
            sa.CheckConstraint("results_count IS NULL OR results_count >= 0", name="ck_app_search_results_nonnegative"),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
            sa.PrimaryKeyConstraint("event_id"),
        )
        op.create_index("ix_app_search_events_customer_id", "app_search_events", ["customer_id"])
        op.create_index("ix_app_search_events_search_timestamp", "app_search_events", ["search_timestamp"])


def downgrade() -> None:
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    if sa.inspect(bind).has_table("app_search_events"):
        op.drop_table("app_search_events")
    if sa.inspect(bind).has_table("support_tickets"):
        op.drop_table("support_tickets")
    if sa.inspect(bind).has_table("vendor_purchase_orders"):
        op.drop_table("vendor_purchase_orders")
