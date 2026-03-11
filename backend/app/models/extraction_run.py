from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
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

    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="running", server_default="running")

    problem_statement = Column(JSONB, nullable=True)
    main_method = Column(JSONB, nullable=True)
    contributions = Column(JSONB, nullable=True)
    limitations = Column(JSONB, nullable=True)
    evaluation_setup = Column(JSONB, nullable=True)

    raw_llm_response = Column(JSONB, nullable=True)

    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    canonical_document = relationship("CanonicalDocument")
    publish_versions = relationship("PublishVersion", back_populates="source_extraction")