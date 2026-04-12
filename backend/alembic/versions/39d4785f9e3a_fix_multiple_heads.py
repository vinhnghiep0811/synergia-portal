"""fix multiple heads

Revision ID: 39d4785f9e3a
Revises: 5c9ea2b23029, 9a2b5d4c7e81
Create Date: 2026-04-11 13:10:03.714738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39d4785f9e3a'
down_revision: Union[str, Sequence[str], None] = ('5c9ea2b23029', '9a2b5d4c7e81')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
