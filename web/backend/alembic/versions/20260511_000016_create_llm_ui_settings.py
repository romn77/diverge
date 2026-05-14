"""create llm ui settings

Revision ID: 20260511_000016
Revises: 20260508_000013
Create Date: 2026-05-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_000016"
down_revision = "20260508_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("llm_ui_settings"):
        return
    op.create_table(
        "llm_ui_settings",
        sa.Column("setting_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("setting_key"),
    )
    op.bulk_insert(
        sa.table(
            "llm_ui_settings",
            sa.column("setting_key", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.String),
            sa.column("enabled", sa.Boolean),
        ),
        [
            {
                "setting_key": "show_custom_analysis_model_profile",
                "label": "Show Custom profile in analysis",
                "description": (
                    "Allow admins to choose a concrete provider and model from "
                    "the new analysis dialog. Non-admin users never see this option."
                ),
                "enabled": True,
            }
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("llm_ui_settings"):
        op.drop_table("llm_ui_settings")
