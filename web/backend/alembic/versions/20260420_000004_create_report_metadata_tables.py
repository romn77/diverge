"""create report metadata tables

Revision ID: 20260420_000004
Revises: 20260420_000003
Create Date: 2026-04-20 12:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260420_000004"
down_revision = "20260420_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_runs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_runs_owner_generated_at",
        "report_runs",
        ["owner_user_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_report_runs_visibility_generated_at",
        "report_runs",
        ["visibility", "generated_at"],
        unique=False,
    )

    op.create_table(
        "report_files",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("report_id", sa.String(length=255), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("category_key", sa.String(length=32), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
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
        sa.ForeignKeyConstraint(["report_id"], ["report_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_files_report_sort_order",
        "report_files",
        ["report_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_report_files_report_relative_path",
        "report_files",
        ["report_id", "relative_path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_report_files_report_relative_path", table_name="report_files")
    op.drop_index("ix_report_files_report_sort_order", table_name="report_files")
    op.drop_table("report_files")
    op.drop_index("ix_report_runs_visibility_generated_at", table_name="report_runs")
    op.drop_index("ix_report_runs_owner_generated_at", table_name="report_runs")
    op.drop_table("report_runs")
