"""create screener runs table

Revision ID: 20260420_000003
Revises: 20260420_000002
Create Date: 2026-04-20 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260420_000003"
down_revision = "20260420_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screener_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("as_of_date", sa.String(length=10), nullable=True),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_screener_runs_generated_at",
        "screener_runs",
        ["generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_screener_runs_owner_generated_at",
        "screener_runs",
        ["owner_user_id", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_screener_runs_owner_generated_at", table_name="screener_runs")
    op.drop_index("ix_screener_runs_generated_at", table_name="screener_runs")
    op.drop_table("screener_runs")
