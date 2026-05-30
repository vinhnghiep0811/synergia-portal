"""merge migration heads

Revision ID: f24801d7d8f6
Revises: a7c3f2e9b541, b7c2d9e4f1a8
Create Date: 2026-05-30 08:12:13.803803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f24801d7d8f6'
down_revision: Union[str, Sequence[str], None] = ('a7c3f2e9b541', 'b7c2d9e4f1a8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
