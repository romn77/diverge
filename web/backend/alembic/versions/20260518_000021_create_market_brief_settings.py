"""create market brief settings

Revision ID: 20260518_000021
Revises: 20260518_000020
Create Date: 2026-05-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260518_000021"
down_revision = "20260518_000020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("market_brief_settings"):
        return

    op.create_table(
        "market_brief_settings",
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=192), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("scope"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("market_brief_settings"):
        op.drop_table("market_brief_settings")
