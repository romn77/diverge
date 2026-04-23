"""create asset tables

Revision ID: 20260423_000005
Revises: 20260420_000004
Create Date: 2026-04-23 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260423_000005"
down_revision = "20260420_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_accounts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("platform_name", sa.String(length=255), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_asset_accounts_owner_updated_at",
        "asset_accounts",
        ["owner_user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_asset_accounts_owner_platform_account",
        "asset_accounts",
        ["owner_user_id", "platform_name", "account_name"],
        unique=True,
    )

    op.create_table(
        "asset_positions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=False),
        sa.Column("asset_category", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("cost_basis", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("valuation_mode", sa.String(length=32), nullable=False),
        sa.Column("manual_price", sa.Float(), nullable=True),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("market", sa.String(length=64), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("quote_type", sa.String(length=64), nullable=True),
        sa.Column("resolved_name", sa.String(length=255), nullable=True),
        sa.Column("quote_currency", sa.String(length=16), nullable=True),
        sa.Column("vendor", sa.String(length=64), nullable=True),
        sa.Column("mapping_status", sa.String(length=32), nullable=False, server_default=sa.text("'unresolved'")),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["asset_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_asset_positions_owner_updated_at",
        "asset_positions",
        ["owner_user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_asset_positions_owner_ticker_updated_at",
        "asset_positions",
        ["owner_user_id", "ticker", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_asset_positions_account_updated_at",
        "asset_positions",
        ["account_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "asset_valuation_snapshots",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("position_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("quote_currency", sa.String(length=16), nullable=True),
        sa.Column("base_currency", sa.String(length=16), nullable=True),
        sa.Column("fx_rate", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["position_id"], ["asset_positions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_asset_valuation_snapshots_position_captured_at",
        "asset_valuation_snapshots",
        ["position_id", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_valuation_snapshots_position_captured_at",
        table_name="asset_valuation_snapshots",
    )
    op.drop_table("asset_valuation_snapshots")

    op.drop_index("ix_asset_positions_account_updated_at", table_name="asset_positions")
    op.drop_index("ix_asset_positions_owner_ticker_updated_at", table_name="asset_positions")
    op.drop_index("ix_asset_positions_owner_updated_at", table_name="asset_positions")
    op.drop_table("asset_positions")

    op.drop_index("ix_asset_accounts_owner_platform_account", table_name="asset_accounts")
    op.drop_index("ix_asset_accounts_owner_updated_at", table_name="asset_accounts")
    op.drop_table("asset_accounts")
