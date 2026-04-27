"""create tenants and assign users

Revision ID: 20260427_000009
Revises: 20260427_000008
Create Date: 2026-04-27 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260427_000009"
down_revision = "20260427_000008"
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = "default"
DEFAULT_TENANT_NAME = "Default Workspace"
DEFAULT_TENANT_SLUG = "default"


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_status", "tenants", ["status"], unique=False)
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, status) "
            "VALUES (:id, :name, :slug, 'active')"
        ).bindparams(
            id=DEFAULT_TENANT_ID,
            name=DEFAULT_TENANT_NAME,
            slug=DEFAULT_TENANT_SLUG,
        )
    )

    op.add_column(
        "users",
        sa.Column("tenant_id", sa.String(length=32), nullable=True, server_default=DEFAULT_TENANT_ID),
    )
    op.execute(
        sa.text("UPDATE users SET tenant_id = :tenant_id WHERE tenant_id IS NULL").bindparams(
            tenant_id=DEFAULT_TENANT_ID
        )
    )
    op.create_index("ix_users_tenant_email", "users", ["tenant_id", "email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_tenant_email", table_name="users")
    op.drop_column("users", "tenant_id")
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
