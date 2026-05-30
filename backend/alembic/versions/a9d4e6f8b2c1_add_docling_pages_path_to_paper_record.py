"""add docling pages path to paper records

Revision ID: a9d4e6f8b2c1
Revises: f24801d7d8f6
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9d4e6f8b2c1"
down_revision: Union[str, Sequence[str], None] = "f24801d7d8f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("paper_records")}

    if "docling_page_text_json_storage_path" not in existing_columns:
        op.add_column(
            "paper_records",
            sa.Column("docling_page_text_json_storage_path", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("paper_records")}

    if "docling_page_text_json_storage_path" in existing_columns:
        op.drop_column("paper_records", "docling_page_text_json_storage_path")
