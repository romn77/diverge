"""create llm model tables

Revision ID: 20260428_000012
Revises: 20260427_000011
Create Date: 2026-04-28 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_000012"
down_revision = "20260427_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_configs",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("api_key_env", sa.String(length=128), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("hourly_limit", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("provider"),
    )

    op.create_table(
        "llm_model_configs",
        sa.Column("id", sa.String(length=256), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=192), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("supports_quick", sa.Boolean(), nullable=False),
        sa.Column("supports_deep", sa.Boolean(), nullable=False),
        sa.Column("cost_tier", sa.String(length=32), nullable=False),
        sa.Column("visible_to_roles", sa.String(length=128), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("weekly_limit", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_model_configs_provider", "llm_model_configs", ["provider"], unique=False
    )

    op.create_table(
        "llm_model_profiles",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("default_for_roles", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("profile_id"),
    )

    op.create_table(
        "llm_model_profile_routes",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("route_order", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=192), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "mode", "route_order"),
    )
    op.create_index(
        "ix_llm_model_profile_routes_profile",
        "llm_model_profile_routes",
        ["profile_id"],
        unique=False,
    )

    op.create_table(
        "llm_model_usage",
        sa.Column("usage_date", sa.String(length=10), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=192), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("total_calls", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("hour_key", sa.String(length=13), nullable=True),
        sa.Column("hour_total_calls", sa.Integer(), nullable=False),
        sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("usage_date", "provider", "model_id", "module"),
    )
    op.create_index(
        "ix_llm_model_usage_provider_model_date",
        "llm_model_usage",
        ["provider", "model_id", "usage_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_llm_model_usage_provider_model_date", table_name="llm_model_usage"
    )
    op.drop_table("llm_model_usage")
    op.drop_index(
        "ix_llm_model_profile_routes_profile", table_name="llm_model_profile_routes"
    )
    op.drop_table("llm_model_profile_routes")
    op.drop_table("llm_model_profiles")
    op.drop_index("ix_llm_model_configs_provider", table_name="llm_model_configs")
    op.drop_table("llm_model_configs")
    op.drop_table("llm_provider_configs")
