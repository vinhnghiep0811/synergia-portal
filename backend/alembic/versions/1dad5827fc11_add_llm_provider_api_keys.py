"""add_llm_provider_api_keys

Revision ID: 1dad5827fc11
Revises: f8c2d7a1b2c3
Create Date: 2026-05-29 12:42:46.182500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1dad5827fc11'
down_revision: Union[str, Sequence[str], None] = 'f8c2d7a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create new table
    op.create_table(
        "llm_provider_api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("provider_name", name="uq_llm_provider_api_keys_provider_name"),
    )

    # 2. Migrate existing data
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT llm_provider, llm_api_key, updated_by_user_id FROM admin_system_configs LIMIT 1")
    ).fetchone()

    if result and result[0] and result[1]:
        provider = result[0]
        api_key = result[1]
        user_id = result[2]
        
        insert_query = sa.text(
            "INSERT INTO llm_provider_api_keys (provider_name, api_key, updated_by_user_id) "
            "VALUES (:provider, :api_key, :user_id)"
        )
        conn.execute(insert_query, {"provider": provider, "api_key": api_key, "user_id": user_id})

    # 3. Drop old column
    op.drop_column("admin_system_configs", "llm_api_key")


def downgrade() -> None:
    # 1. Re-add old column
    op.add_column("admin_system_configs", sa.Column("llm_api_key", sa.Text(), nullable=True))

    # 2. Migrate data back (best effort - get the key for the current provider)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT llm_provider FROM admin_system_configs LIMIT 1")
    ).fetchone()

    if result and result[0]:
        provider = result[0]
        key_result = conn.execute(
            sa.text("SELECT api_key FROM llm_provider_api_keys WHERE provider_name = :provider"),
            {"provider": provider}
        ).fetchone()

        if key_result and key_result[0]:
            api_key = key_result[0]
            conn.execute(
                sa.text("UPDATE admin_system_configs SET llm_api_key = :api_key"),
                {"api_key": api_key}
            )

    # 3. Drop new table
    op.drop_table("llm_provider_api_keys")
