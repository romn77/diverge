"""create search quota tables

Revision ID: 20260508_000013
Revises: 20260506_000015
Create Date: 2026-05-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260508_000013"
down_revision = "20260506_000015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("search_global_configs"):
        op.create_table(
            "search_global_configs",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("disabled_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disabled_reason", sa.String(length=255), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    if not inspector.has_table("search_provider_configs"):
        op.create_table(
            "search_provider_configs",
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("monthly_free_quota", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("monthly_hard_cap", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("disabled_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disabled_reason", sa.String(length=255), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("provider"),
        )
        op.create_index(
            "ix_search_provider_configs_provider",
            "search_provider_configs",
            ["provider"],
        )
    if not inspector.has_table("search_provider_usage"):
        op.create_table(
            "search_provider_usage",
            sa.Column("usage_month", sa.String(length=7), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.String(length=512), nullable=True),
            sa.PrimaryKeyConstraint("usage_month", "provider"),
        )
        op.create_index(
            "ix_search_provider_usage_provider_month",
            "search_provider_usage",
            ["provider", "usage_month"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("search_provider_usage"):
        op.drop_index(
            "ix_search_provider_usage_provider_month",
            table_name="search_provider_usage",
        )
        op.drop_table("search_provider_usage")
    if inspector.has_table("search_provider_configs"):
        op.drop_index(
            "ix_search_provider_configs_provider",
            table_name="search_provider_configs",
        )
        op.drop_table("search_provider_configs")
    if inspector.has_table("search_global_configs"):
        op.drop_table("search_global_configs")
