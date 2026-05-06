"""create llm module settings

Revision ID: 20260506_000014
Revises: 20260430_000013
Create Date: 2026-05-06 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_000014"
down_revision = "20260430_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("llm_module_settings"):
        existing_columns = {
            column["name"]
            for column in inspector.get_columns("llm_module_settings")
        }
        expected_columns = {
            "module": sa.Column("module", sa.String(length=64), nullable=False),
            "enabled": sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            "model_profile": sa.Column("model_profile", sa.String(length=64), nullable=False, server_default="balanced"),
            "output_language": sa.Column("output_language", sa.String(length=8), nullable=False, server_default="cn"),
            "custom_provider": sa.Column("custom_provider", sa.String(length=64), nullable=True),
            "custom_model": sa.Column("custom_model", sa.String(length=192), nullable=True),
            "openai_reasoning_effort": sa.Column("openai_reasoning_effort", sa.String(length=16), nullable=True),
            "google_thinking_level": sa.Column("google_thinking_level", sa.String(length=16), nullable=True),
            "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        }
        for name, column in expected_columns.items():
            if name not in existing_columns:
                op.add_column("llm_module_settings", column)
        return

    op.create_table(
        "llm_module_settings",
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("model_profile", sa.String(length=64), nullable=False),
        sa.Column("output_language", sa.String(length=8), nullable=False),
        sa.Column("custom_provider", sa.String(length=64), nullable=True),
        sa.Column("custom_model", sa.String(length=192), nullable=True),
        sa.Column("openai_reasoning_effort", sa.String(length=16), nullable=True),
        sa.Column("google_thinking_level", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("module"),
    )


def downgrade() -> None:
    op.drop_table("llm_module_settings")
