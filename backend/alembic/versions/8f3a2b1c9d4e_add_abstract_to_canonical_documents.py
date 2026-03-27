"""add abstract to canonical_documents

Revision ID: 8f3a2b1c9d4e
Revises: 253f4900c2c1
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3a2b1c9d4e'
down_revision: Union[str, Sequence[str], None] = '253f4900c2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("canonical_documents")}

    if "abstract" not in existing_columns:
        op.add_column(
            'canonical_documents',
            sa.Column('abstract', sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("canonical_documents")}

    if "abstract" in existing_columns:
        op.drop_column('canonical_documents', 'abstract')