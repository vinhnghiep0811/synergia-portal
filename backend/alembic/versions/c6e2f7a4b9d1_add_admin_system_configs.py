"""add admin system configs

Revision ID: c6e2f7a4b9d1
Revises: a806cc7579f8
Create Date: 2026-05-14 10:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6e2f7a4b9d1"
down_revision: Union[str, Sequence[str], None] = "a806cc7579f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_system_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semantic_scholar_api_key", sa.Text(), nullable=True),
        sa.Column(
            "llm_provider",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'gemini'"),
        ),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata_match_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.7"),
        ),
        sa.Column(
            "pipeline_retry_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "pipeline_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("300"),
        ),
        sa.Column(
            "telegram_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("telegram_bot_token", sa.Text(), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=255), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_system_configs_updated_by_user_id",
        "admin_system_configs",
        ["updated_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_system_configs_updated_by_user_id", table_name="admin_system_configs")
    op.drop_table("admin_system_configs")
