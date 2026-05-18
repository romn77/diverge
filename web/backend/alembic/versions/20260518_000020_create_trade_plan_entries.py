"""create trade plan entries table

Revision ID: 20260518_000020
Revises: 20260515_000019
Create Date: 2026-05-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260518_000020"
down_revision = "20260515_000019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_plan_entries",
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_trade_id", sa.String(length=32), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
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
        sa.PrimaryKeyConstraint("plan_id"),
    )
    op.create_index(
        "ix_trade_plan_entries_tenant_updated_at",
        "trade_plan_entries",
        ["tenant_id", "updated_at"],
    )
    op.create_index(
        "ix_trade_plan_entries_owner_updated_at",
        "trade_plan_entries",
        ["owner_user_id", "updated_at"],
    )
    op.create_index(
        "ix_trade_plan_entries_tenant_owner_status_expires",
        "trade_plan_entries",
        ["tenant_id", "owner_user_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_trade_plan_entries_tenant_owner_ticker_status",
        "trade_plan_entries",
        ["tenant_id", "owner_user_id", "ticker", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trade_plan_entries_tenant_owner_ticker_status",
        table_name="trade_plan_entries",
    )
    op.drop_index(
        "ix_trade_plan_entries_tenant_owner_status_expires",
        table_name="trade_plan_entries",
    )
    op.drop_index(
        "ix_trade_plan_entries_owner_updated_at",
        table_name="trade_plan_entries",
    )
    op.drop_index(
        "ix_trade_plan_entries_tenant_updated_at",
        table_name="trade_plan_entries",
    )
    op.drop_table("trade_plan_entries")
