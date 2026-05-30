"""merge heads and extend llm_provider_options name to 255

Revision ID: a7c3f2e9b541
Revises: b3e6c1a2f7d4, f1a8b6c0d7e2
Create Date: 2026-05-30 10:00:00.000000

Merges:
 - b3e6c1a2f7d4 (add_llm_provider_configs)
 - f1a8b6c0d7e2 (add_llm_prompts_and_providers)

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3f2e9b541"
down_revision: Union[str, Sequence[str], None] = ("b3e6c1a2f7d4", "f1a8b6c0d7e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend model name column to support long OpenRouter model slugs
    # e.g. "anthropic/claude-opus-4-5:thinking" is >50 chars
    op.alter_column(
        "llm_provider_options",
        "name",
        type_=sa.String(length=255),
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "llm_provider_options",
        "name",
        type_=sa.String(length=50),
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
