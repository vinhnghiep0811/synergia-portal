"""add crossref verification to canonical documents

Revision ID: b7c2d9e4f1a8
Revises: c6e2f7a4b9d1
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7c2d9e4f1a8"
down_revision: Union[str, Sequence[str], None] = "c6e2f7a4b9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("canonical_documents")}

    if "crossref_match_status" not in existing_columns:
        op.add_column(
            "canonical_documents",
            sa.Column("crossref_match_status", sa.String(length=30), nullable=True),
        )
    if "crossref_match_confidence" not in existing_columns:
        op.add_column(
            "canonical_documents",
            sa.Column("crossref_match_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        )
    if "crossref_metadata_json" not in existing_columns:
        op.add_column(
            "canonical_documents",
            sa.Column("crossref_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "crossref_verification_json" not in existing_columns:
        op.add_column(
            "canonical_documents",
            sa.Column("crossref_verification_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("canonical_documents")}

    if "crossref_verification_json" in existing_columns:
        op.drop_column("canonical_documents", "crossref_verification_json")
    if "crossref_metadata_json" in existing_columns:
        op.drop_column("canonical_documents", "crossref_metadata_json")
    if "crossref_match_confidence" in existing_columns:
        op.drop_column("canonical_documents", "crossref_match_confidence")
    if "crossref_match_status" in existing_columns:
        op.drop_column("canonical_documents", "crossref_match_status")
