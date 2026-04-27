"""create user permissions table

Revision ID: 20260427_000008
Revises: 20260426_000007
Create Date: 2026-04-27 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260427_000008"
down_revision = "20260426_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_permissions_user_permission",
        "user_permissions",
        ["user_id", "permission"],
        unique=True,
    )
    op.create_index(
        "ix_user_permissions_user_effect",
        "user_permissions",
        ["user_id", "effect"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_permissions_user_effect", table_name="user_permissions")
    op.drop_index("ix_user_permissions_user_permission", table_name="user_permissions")
    op.drop_table("user_permissions")
