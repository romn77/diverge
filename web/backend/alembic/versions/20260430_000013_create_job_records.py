"""create job records table

Revision ID: 20260430_000013
Revises: 20260428_000012
Create Date: 2026-04-30 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260430_000013"
down_revision = "20260428_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_records_kind_status", "job_records", ["kind", "status"], unique=False
    )
    op.create_index(
        "ix_job_records_tenant_status",
        "job_records",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_job_records_owner_status",
        "job_records",
        ["owner_user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_job_records_updated_at", "job_records", ["updated_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_job_records_updated_at", table_name="job_records")
    op.drop_index("ix_job_records_owner_status", table_name="job_records")
    op.drop_index("ix_job_records_tenant_status", table_name="job_records")
    op.drop_index("ix_job_records_kind_status", table_name="job_records")
    op.drop_table("job_records")
