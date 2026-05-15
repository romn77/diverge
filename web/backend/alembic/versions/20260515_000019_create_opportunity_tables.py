"""create opportunity radar tables

Revision ID: 20260515_000019
Revises: 20260514_000018
Create Date: 2026-05-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260515_000019"
down_revision = "20260514_000018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_runs",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.String(length=32), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_manifest", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opportunity_runs_tenant_trade_date",
        "opportunity_runs",
        ["tenant_id", "trade_date"],
    )
    op.create_index(
        "ix_opportunity_runs_config",
        "opportunity_runs",
        ["tenant_id", "market", "trade_date", "config_hash"],
    )
    op.create_index(
        "ix_opportunity_runs_generated_at", "opportunity_runs", ["generated_at"]
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.String(length=32), nullable=True),
        sa.Column("strategy_id", sa.String(length=128), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_manifest", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_runs_tenant_strategy",
        "backtest_runs",
        ["tenant_id", "strategy_id"],
    )
    op.create_index("ix_backtest_runs_generated_at", "backtest_runs", ["generated_at"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("theme_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_run_id", sa.String(length=96), nullable=True),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watchlist_items_owner_symbol",
        "watchlist_items",
        ["owner_user_id", "symbol"],
        unique=True,
    )
    op.create_index(
        "ix_watchlist_items_tenant_status", "watchlist_items", ["tenant_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_tenant_status", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_owner_symbol", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_backtest_runs_generated_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_tenant_strategy", table_name="backtest_runs")
    op.drop_table("backtest_runs")
    op.drop_index("ix_opportunity_runs_generated_at", table_name="opportunity_runs")
    op.drop_index("ix_opportunity_runs_config", table_name="opportunity_runs")
    op.drop_index(
        "ix_opportunity_runs_tenant_trade_date", table_name="opportunity_runs"
    )
    op.drop_table("opportunity_runs")
