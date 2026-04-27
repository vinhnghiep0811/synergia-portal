import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CitationMention(Base):
    __tablename__ = "citation_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("citation_score_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_canonical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_canonical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_section_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    anchor_text = Column(String(255), nullable=True)
    context_snippet = Column(Text, nullable=False)
    page_from = Column(Integer, nullable=True)
    page_to = Column(Integer, nullable=True)

    section_type = Column(String(50), nullable=True)
    section_weight = Column(Numeric(5, 4), nullable=False)

    link_method = Column(String(50), nullable=True)
    link_confidence = Column(Numeric(5, 4), nullable=False)
    semantic_similarity = Column(Numeric(5, 4), nullable=False)

    intent_label = Column(String(50), nullable=False)
    intent_score = Column(Numeric(5, 4), nullable=False)

    chunk_quality = Column(Numeric(5, 4), nullable=False)
    mention_score = Column(Numeric(5, 4), nullable=False, index=True)

    is_internal = Column(Boolean, nullable=False, default=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("CitationScoreRun", back_populates="mentions")
    source_canonical_document = relationship(
        "CanonicalDocument",
        foreign_keys=[source_canonical_id],
        back_populates="citation_mentions_source",
    )
    target_canonical_document = relationship(
        "CanonicalDocument",
        foreign_keys=[target_canonical_id],
        back_populates="citation_mentions_target",
    )
    source_chunk = relationship(
        "DocumentChunk",
        foreign_keys=[source_chunk_id],
        back_populates="citation_mentions",
    )
    source_section = relationship(
        "DocumentSection",
        foreign_keys=[source_section_id],
        back_populates="citation_mentions",
    )
