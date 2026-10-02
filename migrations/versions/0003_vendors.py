"""Add normalized vendor master and link product and PO vendor IDs.

Revision ID: 0003_vendors
Revises: 0001_initial
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0003_vendors"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _has_fk(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        column_name in fk["constrained_columns"] and fk["referred_table"] == "vendors"
        for fk in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    # The initial revision uses current SQLAlchemy metadata in its offline
    # script, so it already emits the final schema, including this revision.
    # Online upgrades from an older 0001 database still use the guarded DDL below.
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("vendors"):
        op.create_table(
            "vendors",
            sa.Column("vendor_id", sa.String(), nullable=False),
            sa.Column("vendor_name", sa.String(), nullable=False),
            sa.Column("city", sa.String(), nullable=False),
            sa.Column("lead_time_days", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.PrimaryKeyConstraint("vendor_id"),
        )
        existing = sa.inspect(bind)
        for source in ("products", "product_size_chart", "vendor_purchase_orders"):
            if existing.has_table(source) and "vendor_id" in {c["name"] for c in existing.get_columns(source)}:
                bind.execute(sa.text(f"""
                    INSERT INTO vendors (vendor_id, vendor_name, city)
                    SELECT DISTINCT vendor_id, 'Unknown', 'Unknown' FROM {source}
                    ON CONFLICT (vendor_id) DO NOTHING
                """))

    inspector = sa.inspect(bind)
    if inspector.has_table("products") and not _has_fk("products", "vendor_id"):
        op.create_foreign_key("fk_products_vendor_id_vendors", "products", "vendors", ["vendor_id"], ["vendor_id"])
    inspector = sa.inspect(bind)
    if inspector.has_table("vendor_purchase_orders") and not _has_fk("vendor_purchase_orders", "vendor_id"):
        op.create_foreign_key("fk_vendor_po_vendor_id_vendors", "vendor_purchase_orders", "vendors", ["vendor_id"], ["vendor_id"])
    inspector = sa.inspect(bind)
    if inspector.has_table("product_size_chart") and not _has_fk("product_size_chart", "vendor_id"):
        op.create_foreign_key("fk_product_size_chart_vendor_id_vendors", "product_size_chart", "vendors", ["vendor_id"], ["vendor_id"])


def downgrade() -> None:
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("vendor_purchase_orders") and _has_fk("vendor_purchase_orders", "vendor_id"):
        op.drop_constraint("fk_vendor_po_vendor_id_vendors", "vendor_purchase_orders", type_="foreignkey")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("products") and _has_fk("products", "vendor_id"):
        op.drop_constraint("fk_products_vendor_id_vendors", "products", type_="foreignkey")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("product_size_chart") and _has_fk("product_size_chart", "vendor_id"):
        op.drop_constraint("fk_product_size_chart_vendor_id_vendors", "product_size_chart", type_="foreignkey")
    if sa.inspect(op.get_bind()).has_table("vendors"):
        op.drop_table("vendors")
