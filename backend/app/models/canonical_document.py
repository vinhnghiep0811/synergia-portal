from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CanonicalDocument(Base):
    __tablename__ = "canonical_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    canonical_key = Column(String(255), nullable=False, unique=True, index=True)
    canonical_type = Column(String(20), nullable=False)  # DOI | FINGERPRINT

    doi = Column(String(255), nullable=True, unique=True)
    fingerprint = Column(String(255), nullable=True, unique=True)

    title_candidate = Column(Text, nullable=True)
    normalized_title = Column(Text, nullable=True)

    ss_paper_id = Column(String(255), nullable=True)
    ss_match_confidence = Column(Numeric(5, 4), nullable=True)
    metadata_source = Column(String(50), nullable=True)

    title = Column(Text, nullable=True)
    abstract = Column(Text, nullable=True)
    venue = Column(Text, nullable=True)
    publication_year = Column(Integer, nullable=True)

    authors_json = Column(JSONB, nullable=True)
    references_json = Column(JSONB, nullable=True)

    enrichment_status = Column(String(30), nullable=False, default="pending", server_default="pending")
    extraction_cache_status = Column(String(30), nullable=False, default="empty", server_default="empty")
    match_status = Column(String(30), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    papers = relationship("PaperRecord", back_populates="canonical_document", lazy="selectin")
    extraction_runs = relationship(
        "ExtractionRun",
        back_populates="canonical_document",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ExtractionRun.canonical_document_id",
    )
    latest_extraction_run_id = Column(UUID(as_uuid=True), ForeignKey("extraction_runs.id"), nullable=True)
    latest_extraction_run = relationship(
        "ExtractionRun",
        foreign_keys=[latest_extraction_run_id],
        post_update=True,
    )

    document_sections = relationship(
        "DocumentSection",
        back_populates="canonical_document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    document_chunks = relationship(
        "DocumentChunk",
        back_populates="canonical_document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    