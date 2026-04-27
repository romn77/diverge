"""add tenant ids to workbench tables

Revision ID: 20260427_000010
Revises: 20260427_000009
Create Date: 2026-04-27 16:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260427_000010"
down_revision = "20260427_000009"
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = "default"


OWNER_TABLES = (
    ("report_runs", "owner_user_id"),
    ("screener_runs", "owner_user_id"),
    ("trade_entries", "owner_user_id"),
    ("asset_accounts", "owner_user_id"),
    ("asset_positions", "owner_user_id"),
    ("analysis_task_usage", "user_id"),
)


def _add_tenant_column(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column("tenant_id", sa.String(length=32), nullable=True, server_default=DEFAULT_TENANT_ID),
    )


def _backfill_from_owner(table_name: str, owner_column: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET tenant_id = COALESCE(
                (SELECT users.tenant_id FROM users WHERE users.id = {table_name}.{owner_column}),
                :default_tenant_id
            )
            WHERE tenant_id IS NULL OR tenant_id = :default_tenant_id
            """
        ).bindparams(default_tenant_id=DEFAULT_TENANT_ID)
    )


def upgrade() -> None:
    for table_name, owner_column in OWNER_TABLES:
        _add_tenant_column(table_name)
        _backfill_from_owner(table_name, owner_column)

    _add_tenant_column("asset_valuation_snapshots")
    op.execute(
        sa.text(
            """
            UPDATE asset_valuation_snapshots
            SET tenant_id = COALESCE(
                (
                    SELECT asset_positions.tenant_id
                    FROM asset_positions
                    WHERE asset_positions.id = asset_valuation_snapshots.position_id
                ),
                :default_tenant_id
            )
            WHERE tenant_id IS NULL OR tenant_id = :default_tenant_id
            """
        ).bindparams(default_tenant_id=DEFAULT_TENANT_ID)
    )

    op.create_index("ix_report_runs_tenant_generated_at", "report_runs", ["tenant_id", "generated_at"], unique=False)
    op.create_index(
        "ix_report_runs_tenant_visibility_generated_at",
        "report_runs",
        ["tenant_id", "visibility", "generated_at"],
        unique=False,
    )
    op.create_index("ix_screener_runs_tenant_generated_at", "screener_runs", ["tenant_id", "generated_at"], unique=False)
    op.create_index("ix_trade_entries_tenant_updated_at", "trade_entries", ["tenant_id", "updated_at"], unique=False)
    op.create_index("ix_asset_accounts_tenant_updated_at", "asset_accounts", ["tenant_id", "updated_at"], unique=False)
    op.create_index("ix_asset_positions_tenant_updated_at", "asset_positions", ["tenant_id", "updated_at"], unique=False)
    op.create_index(
        "ix_asset_valuation_snapshots_tenant_captured_at",
        "asset_valuation_snapshots",
        ["tenant_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_task_usage_tenant_user_module_week",
        "analysis_task_usage",
        ["tenant_id", "user_id", "module", "usage_week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_task_usage_tenant_user_module_week", table_name="analysis_task_usage")
    op.drop_index("ix_asset_valuation_snapshots_tenant_captured_at", table_name="asset_valuation_snapshots")
    op.drop_index("ix_asset_positions_tenant_updated_at", table_name="asset_positions")
    op.drop_index("ix_asset_accounts_tenant_updated_at", table_name="asset_accounts")
    op.drop_index("ix_trade_entries_tenant_updated_at", table_name="trade_entries")
    op.drop_index("ix_screener_runs_tenant_generated_at", table_name="screener_runs")
    op.drop_index("ix_report_runs_tenant_visibility_generated_at", table_name="report_runs")
    op.drop_index("ix_report_runs_tenant_generated_at", table_name="report_runs")
    op.drop_column("asset_valuation_snapshots", "tenant_id")
    for table_name, _owner_column in reversed(OWNER_TABLES):
        op.drop_column(table_name, "tenant_id")
