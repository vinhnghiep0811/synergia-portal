"""add publish draft fields to paper_records

Revision ID: 9a2b5d4c7e81
Revises: d63e55a1e089
Create Date: 2026-04-09 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9a2b5d4c7e81"
down_revision: Union[str, Sequence[str], None] = "d63e55a1e089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("paper_records", sa.Column("publish_title_draft", sa.Text(), nullable=True))
    op.add_column("paper_records", sa.Column("publish_abstract_draft", sa.Text(), nullable=True))
    op.add_column("paper_records", sa.Column("publish_venue_draft", sa.Text(), nullable=True))
    op.add_column("paper_records", sa.Column("publish_year_draft", sa.Integer(), nullable=True))
    op.add_column(
        "paper_records",
        sa.Column("publish_authors_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("paper_records", sa.Column("publish_problem_statement_draft", sa.Text(), nullable=True))
    op.add_column("paper_records", sa.Column("publish_main_method_draft", sa.Text(), nullable=True))
    op.add_column(
        "paper_records",
        sa.Column("publish_contributions_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "paper_records",
        sa.Column("publish_limitations_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "paper_records",
        sa.Column("publish_evaluation_setup_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("paper_records", "publish_evaluation_setup_draft")
    op.drop_column("paper_records", "publish_limitations_draft")
    op.drop_column("paper_records", "publish_contributions_draft")
    op.drop_column("paper_records", "publish_main_method_draft")
    op.drop_column("paper_records", "publish_problem_statement_draft")
    op.drop_column("paper_records", "publish_authors_draft")
    op.drop_column("paper_records", "publish_year_draft")
    op.drop_column("paper_records", "publish_venue_draft")
    op.drop_column("paper_records", "publish_abstract_draft")
    op.drop_column("paper_records", "publish_title_draft")
