"""add username login identifiers

Revision ID: 20260514_000018
Revises: 20260512_000017
Create Date: 2026-05-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_000018"
down_revision = "20260512_000017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("username", sa.String(length=320), nullable=True),
    )
    op.execute(sa.text("UPDATE users SET username = lower(email) WHERE username IS NULL"))

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "username",
                existing_type=sa.String(length=320),
                nullable=False,
            )
            batch_op.create_index("ix_users_username", ["username"], unique=False)
            batch_op.create_index(
                "ix_users_tenant_username",
                ["tenant_id", "username"],
                unique=True,
            )
        return

    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=320),
        nullable=False,
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index(
        "ix_users_tenant_username",
        "users",
        ["tenant_id", "username"],
        unique=True,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_index("ix_users_tenant_username")
            batch_op.drop_index("ix_users_username")
            batch_op.drop_column("username")
        return

    op.drop_index("ix_users_tenant_username", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
