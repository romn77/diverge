"""create data source tables

Revision ID: 20260426_000007
Revises: 20260425_000006
Create Date: 2026-04-26 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260426_000007"
down_revision = "20260425_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_source_vendor_configs",
        sa.Column("vendor", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("hourly_limit", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("vendor"),
    )

    op.create_table(
        "data_source_usage",
        sa.Column("usage_date", sa.String(length=10), nullable=False),
        sa.Column("vendor", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hour_key", sa.String(length=13), nullable=True),
        sa.Column("hour_total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("usage_date", "vendor", "module"),
    )
    op.create_table(
        "data_source_route_policies",
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("vendor_chain", sa.String(length=512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("module", "market", "category"),
    )
    op.create_index(
        "ix_data_source_route_policies_module_market",
        "data_source_route_policies",
        ["module", "market"],
        unique=False,
    )
    op.create_index(
        "ix_data_source_usage_date_vendor",
        "data_source_usage",
        ["usage_date", "vendor"],
        unique=False,
    )
    op.create_index(
        "ix_data_source_usage_module_date",
        "data_source_usage",
        ["module", "usage_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_data_source_usage_module_date", table_name="data_source_usage")
    op.drop_index("ix_data_source_usage_date_vendor", table_name="data_source_usage")
    op.drop_index(
        "ix_data_source_route_policies_module_market",
        table_name="data_source_route_policies",
    )
    op.drop_table("data_source_route_policies")
    op.drop_table("data_source_usage")
    op.drop_table("data_source_vendor_configs")
