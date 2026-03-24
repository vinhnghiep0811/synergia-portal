"""add detected fingerprint to paper records

Revision ID: 253f4900c2c1
Revises: 67850aad9ba8
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '253f4900c2c1'
down_revision: Union[str, Sequence[str], None] = '67850aad9ba8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'paper_records',
        sa.Column('detected_fingerprint', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('paper_records', 'detected_fingerprint')
