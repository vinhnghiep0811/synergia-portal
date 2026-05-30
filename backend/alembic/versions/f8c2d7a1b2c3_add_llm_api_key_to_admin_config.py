"""add llm api key to admin config

Revision ID: f8c2d7a1b2c3
Revises: f1a8b6c0d7e2
Create Date: 2026-05-29 10:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8c2d7a1b2c3"
down_revision: Union[str, Sequence[str], None] = "f1a8b6c0d7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_system_configs", sa.Column("llm_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_system_configs", "llm_api_key")
