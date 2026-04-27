"""add citation graph tables

Revision ID: f4b6c9e2a731
Revises: d95e0b7ed581
Create Date: 2026-04-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f4b6c9e2a731"
down_revision: Union[str, Sequence[str], None] = "d95e0b7ed581"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "citation_score_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=50), nullable=False),
        sa.Column("weights_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="running", nullable=False),
        sa.Column("processed_mentions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_edges", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_citation_score_runs_algorithm_version"),
        "citation_score_runs",
        ["algorithm_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_score_runs_status"),
        "citation_score_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "citation_mentions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("source_canonical_id", sa.UUID(), nullable=False),
        sa.Column("target_canonical_id", sa.UUID(), nullable=True),
        sa.Column("source_chunk_id", sa.UUID(), nullable=True),
        sa.Column("source_section_id", sa.UUID(), nullable=True),
        sa.Column("anchor_text", sa.String(length=255), nullable=True),
        sa.Column("context_snippet", sa.Text(), nullable=False),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("section_type", sa.String(length=50), nullable=True),
        sa.Column("section_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("link_method", sa.String(length=50), nullable=True),
        sa.Column("link_confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("semantic_similarity", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("intent_label", sa.String(length=50), nullable=False),
        sa.Column("intent_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("chunk_quality", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("mention_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["citation_score_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_canonical_id"], ["canonical_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_canonical_id"], ["canonical_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_section_id"], ["document_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_citation_mentions_run_id"), "citation_mentions", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_citation_mentions_source_canonical_id"),
        "citation_mentions",
        ["source_canonical_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_mentions_target_canonical_id"),
        "citation_mentions",
        ["target_canonical_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_mentions_source_chunk_id"),
        "citation_mentions",
        ["source_chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_mentions_source_section_id"),
        "citation_mentions",
        ["source_section_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_mentions_mention_score"),
        "citation_mentions",
        ["mention_score"],
        unique=False,
    )

    op.create_table(
        "citation_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=50), nullable=False),
        sa.Column("source_canonical_id", sa.UUID(), nullable=False),
        sa.Column("target_canonical_id", sa.UUID(), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False),
        sa.Column("top3_mean_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("frequency_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("diversity_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("intent_edge_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("citation_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("score_band", sa.String(length=20), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["citation_score_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_canonical_id"], ["canonical_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_canonical_id"], ["canonical_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "source_canonical_id",
            "target_canonical_id",
            name="uq_citation_edges_run_source_target",
        ),
    )
    op.create_index(op.f("ix_citation_edges_run_id"), "citation_edges", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_citation_edges_algorithm_version"),
        "citation_edges",
        ["algorithm_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_edges_source_canonical_id"),
        "citation_edges",
        ["source_canonical_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_edges_target_canonical_id"),
        "citation_edges",
        ["target_canonical_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_edges_citation_score"),
        "citation_edges",
        ["citation_score"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_citation_edges_citation_score"), table_name="citation_edges")
    op.drop_index(op.f("ix_citation_edges_target_canonical_id"), table_name="citation_edges")
    op.drop_index(op.f("ix_citation_edges_source_canonical_id"), table_name="citation_edges")
    op.drop_index(op.f("ix_citation_edges_algorithm_version"), table_name="citation_edges")
    op.drop_index(op.f("ix_citation_edges_run_id"), table_name="citation_edges")
    op.drop_table("citation_edges")

    op.drop_index(op.f("ix_citation_mentions_mention_score"), table_name="citation_mentions")
    op.drop_index(op.f("ix_citation_mentions_source_section_id"), table_name="citation_mentions")
    op.drop_index(op.f("ix_citation_mentions_source_chunk_id"), table_name="citation_mentions")
    op.drop_index(op.f("ix_citation_mentions_target_canonical_id"), table_name="citation_mentions")
    op.drop_index(op.f("ix_citation_mentions_source_canonical_id"), table_name="citation_mentions")
    op.drop_index(op.f("ix_citation_mentions_run_id"), table_name="citation_mentions")
    op.drop_table("citation_mentions")

    op.drop_index(op.f("ix_citation_score_runs_status"), table_name="citation_score_runs")
    op.drop_index(op.f("ix_citation_score_runs_algorithm_version"), table_name="citation_score_runs")
    op.drop_table("citation_score_runs")
