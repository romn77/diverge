"""create analysis limit tables

Revision ID: 20260425_000006
Revises: 20260423_000005
Create Date: 2026-04-25 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260425_000006"
down_revision = "20260423_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_role_limits",
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("weekly_limit", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("role"),
    )

    op.create_table(
        "analysis_task_usage",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("usage_week", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_task_usage_user_module_week",
        "analysis_task_usage",
        ["user_id", "module", "usage_week"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_task_usage_role_module_week",
        "analysis_task_usage",
        ["role", "module", "usage_week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_task_usage_role_module_week", table_name="analysis_task_usage")
    op.drop_index("ix_analysis_task_usage_user_module_week", table_name="analysis_task_usage")
    op.drop_table("analysis_task_usage")
    op.drop_table("analysis_role_limits")
