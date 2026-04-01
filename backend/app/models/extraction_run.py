from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    canonical_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="running", server_default="running")

    result_json = Column(JSONB, nullable=True)

    problem_statement = Column(JSONB, nullable=True)
    main_method = Column(JSONB, nullable=True)
    contributions = Column(JSONB, nullable=True)
    limitations = Column(JSONB, nullable=True)
    evaluation_setup = Column(JSONB, nullable=True)

    raw_llm_response = Column(JSONB, nullable=True)

    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    is_from_cache = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    canonical_document = relationship(
        "CanonicalDocument",
        back_populates="extraction_runs",
        foreign_keys=[canonical_document_id],
    )
    publish_versions = relationship("PublishVersion", back_populates="source_extraction")