"""add report visibility override fields

Revision ID: 20260512_000017
Revises: 20260511_000016
Create Date: 2026-05-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260512_000017"
down_revision = "20260511_000016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report_runs",
        sa.Column("visibility_updated_by_user_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "report_runs",
        sa.Column("visibility_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_runs",
        sa.Column(
            "visibility_admin_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_foreign_key(
        "fk_report_runs_visibility_updated_by_user_id_users",
        "report_runs",
        "users",
        ["visibility_updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("report_runs", "visibility_admin_override", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "fk_report_runs_visibility_updated_by_user_id_users",
        "report_runs",
        type_="foreignkey",
    )
    op.drop_column("report_runs", "visibility_admin_override")
    op.drop_column("report_runs", "visibility_updated_at")
    op.drop_column("report_runs", "visibility_updated_by_user_id")
