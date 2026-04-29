from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    canonical_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    section_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    chunk_index = Column(Integer, nullable=False)

    section = Column(String(500), nullable=True)
    section_type = Column(String(50), nullable=True)
    section_heading_level = Column(Integer, nullable=True)
    section_full_path = Column(Text, nullable=True)

    is_retrievable = Column(Boolean, nullable=False, default=True)

    page_from = Column(Integer, nullable=True)
    page_to = Column(Integer, nullable=True)

    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(384), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    canonical_document = relationship("CanonicalDocument", back_populates="document_chunks")
    section_ref = relationship("DocumentSection")
    citation_mentions = relationship(
        "CitationMention",
        foreign_keys="CitationMention.source_chunk_id",
        back_populates="source_chunk",
    )