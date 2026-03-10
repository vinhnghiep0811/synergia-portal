from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
import uuid
import sqlalchemy as sa
from app.core.database import Base


class PublishVersion(Base):
    __tablename__ = "publish_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    paper_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("paper_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_extraction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    version_number = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String(20), nullable=False, default="draft", server_default="draft")  # draft | published

    title_override = Column(Text, nullable=True)
    abstract_override = Column(Text, nullable=True)
    venue_override = Column(Text, nullable=True)
    year_override = Column(Integer, nullable=True)
    authors_override = Column(JSONB, nullable=True)

    problem_statement_final = Column(JSONB, nullable=True)
    main_method_final = Column(JSONB, nullable=True)
    contributions_final = Column(JSONB, nullable=True)
    limitations_final = Column(JSONB, nullable=True)
    evaluation_setup_final = Column(JSONB, nullable=True)

    tags = Column(ARRAY(Text), nullable=True)
    note = Column(Text, nullable=True)

    published_by = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    telegram_notified = Column(Boolean, nullable=False, default=False, server_default=sa.text("false"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    paper_record = relationship("PaperRecord", back_populates="publish_versions")
    source_extraction = relationship("ExtractionRun", back_populates="publish_versions")