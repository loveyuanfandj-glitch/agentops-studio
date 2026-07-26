"""Add tenant-scoped operational data used by agent tools."""

import sqlalchemy as sa

from alembic import op

revision = "20260726_03"
down_revision = "20260726_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revenue_summaries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gross_revenue", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_revenue", sa.Numeric(14, 2), nullable=False),
        sa.Column("orders", sa.Integer(), nullable=False),
        sa.Column("refund_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column(
            "change_vs_previous_period_pct", sa.Numeric(8, 3), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_revenue_summaries_lookup",
        "revenue_summaries",
        ["tenant_id", "start_date", "end_date", "channel"],
        unique=True,
    )
    op.create_table(
        "commerce_orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("customer", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("value_usd", sa.Numeric(14, 2), nullable=False),
        sa.Column("risk", sa.String(length=240), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_commerce_orders_tenant_order",
        "commerce_orders",
        ["tenant_id", "order_id"],
        unique=True,
    )
    op.create_index(
        "ix_commerce_orders_tenant_status",
        "commerce_orders",
        ["tenant_id", "status"],
    )
    op.create_table(
        "customer_health",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("segment", sa.String(length=40), nullable=False),
        sa.Column("lifetime_value_usd", sa.Numeric(14, 2), nullable=False),
        sa.Column("open_support_cases", sa.Integer(), nullable=False),
        sa.Column("recommended_action", sa.String(length=300), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_customer_health_tenant_customer",
        "customer_health",
        ["tenant_id", "customer_id"],
        unique=True,
    )
    op.create_table(
        "knowledge_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("section", sa.String(length=120), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_knowledge_records_tenant", "knowledge_records", ["tenant_id"]
    )
    op.create_table(
        "inventory_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("warehouse", sa.String(length=32), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("days_of_cover", sa.Numeric(8, 2), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_inventory_records_tenant_warehouse",
        "inventory_records",
        ["tenant_id", "warehouse"],
    )


def downgrade() -> None:
    op.drop_table("inventory_records")
    op.drop_table("knowledge_records")
    op.drop_table("customer_health")
    op.drop_table("commerce_orders")
    op.drop_table("revenue_summaries")
