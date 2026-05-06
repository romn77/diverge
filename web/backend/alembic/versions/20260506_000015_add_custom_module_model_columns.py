"""add custom module model columns

Revision ID: 20260506_000015
Revises: 20260506_000014
Create Date: 2026-05-06 21:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_000015"
down_revision = "20260506_000014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns("llm_module_settings")
    }
    if "custom_provider" not in existing_columns:
        op.add_column(
            "llm_module_settings",
            sa.Column("custom_provider", sa.String(length=64), nullable=True),
        )
    if "custom_model" not in existing_columns:
        op.add_column(
            "llm_module_settings",
            sa.Column("custom_model", sa.String(length=192), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns("llm_module_settings")
    }
    if "custom_model" in existing_columns:
        op.drop_column("llm_module_settings", "custom_model")
    if "custom_provider" in existing_columns:
        op.drop_column("llm_module_settings", "custom_provider")
