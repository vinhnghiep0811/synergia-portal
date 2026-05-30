"""add llm provider configs

Revision ID: b3e6c1a2f7d4
Revises: 1dad5827fc11
Create Date: 2026-05-29 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3e6c1a2f7d4"
down_revision: Union[str, Sequence[str], None] = "1dad5827fc11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("extra_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.UniqueConstraint("provider_name", name="uq_llm_provider_configs_provider_name"),
    )

    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT llm_provider, llm_model, updated_by_user_id "
            "FROM admin_system_configs LIMIT 1"
        )
    ).fetchone()

    if result and result[0]:
        conn.execute(
            sa.text(
                "INSERT INTO llm_provider_configs (provider_name, model_name, updated_by_user_id) "
                "VALUES (:provider, :model_name, :user_id) "
                "ON CONFLICT (provider_name) DO NOTHING"
            ),
            {
                "provider": result[0],
                "model_name": result[1],
                "user_id": result[2],
            },
        )


def downgrade() -> None:
    op.drop_table("llm_provider_configs")
