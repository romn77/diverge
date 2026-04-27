"""create audit events

Revision ID: 20260427_000011
Revises: 20260427_000010
Create Date: 2026-04-27 16:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260427_000011"
down_revision = "20260427_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("actor_user_id", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_tenant_created_at", "audit_events", ["tenant_id", "created_at"], unique=False)
    op.create_index(
        "ix_audit_events_tenant_action_created_at",
        "audit_events",
        ["tenant_id", "action", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_tenant_actor_created_at",
        "audit_events",
        ["tenant_id", "actor_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_tenant_actor_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_action_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_created_at", table_name="audit_events")
    op.drop_table("audit_events")
