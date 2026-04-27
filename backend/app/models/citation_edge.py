import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CitationEdge(Base):
    __tablename__ = "citation_edges"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "source_canonical_id",
            "target_canonical_id",
            name="uq_citation_edges_run_source_target",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("citation_score_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    algorithm_version = Column(String(50), nullable=False, index=True)

    source_canonical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_canonical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mention_count = Column(Integer, nullable=False)
    top3_mean_score = Column(Numeric(5, 4), nullable=False)
    frequency_score = Column(Numeric(5, 4), nullable=False)
    diversity_score = Column(Numeric(5, 4), nullable=False)
    intent_edge_score = Column(Numeric(5, 4), nullable=False)
    citation_score = Column(Numeric(5, 4), nullable=False, index=True)

    score_band = Column(String(20), nullable=True)
    evidence_json = Column(JSONB, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    run = relationship("CitationScoreRun", back_populates="edges")
    source_canonical_document = relationship(
        "CanonicalDocument",
        foreign_keys=[source_canonical_id],
        back_populates="citation_edges_outgoing",
    )
    target_canonical_document = relationship(
        "CanonicalDocument",
        foreign_keys=[target_canonical_id],
        back_populates="citation_edges_incoming",
    )
