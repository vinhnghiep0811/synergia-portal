"""add role to users

Revision ID: 5c9ea2b23029
Revises: d63e55a1e089
Create Date: 2026-04-09 16:11:49.643747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c9ea2b23029'
down_revision: Union[str, Sequence[str], None] = 'd63e55a1e089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), nullable=True, server_default='user')
    )

    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")

    op.alter_column(
        'users',
        'role',
        existing_type=sa.String(length=20),
        nullable=False,
        server_default='user'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'role')