"""create trade entries table

Revision ID: 20260420_000002
Revises: 20260420_000001
Create Date: 2026-04-20 11:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260420_000002"
down_revision = "20260420_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_entries",
        sa.Column("trade_id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "review_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trade_id"),
    )
    op.create_index(
        "ix_trade_entries_owner_ticker_updated_at",
        "trade_entries",
        ["owner_user_id", "ticker", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_trade_entries_owner_updated_at",
        "trade_entries",
        ["owner_user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trade_entries_owner_updated_at", table_name="trade_entries")
    op.drop_index(
        "ix_trade_entries_owner_ticker_updated_at",
        table_name="trade_entries",
    )
    op.drop_table("trade_entries")
