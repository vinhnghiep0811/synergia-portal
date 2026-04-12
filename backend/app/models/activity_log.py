import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    actor_type = Column(String(20), nullable=False)  # user | system
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    event_type = Column(String(100), nullable=False, index=True)

    object_type = Column(String(50), nullable=False)  # paper_record | canonical_document | extraction_run
    object_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    paper_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("paper_records.id"),
        nullable=True,
        index=True,
    )

    canonical_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id"),
        nullable=True,
        index=True,
    )

    status = Column(String(20), nullable=False, index=True)  # info | success | warning | error
    message = Column(Text, nullable=False)

    metadata_json = Column(JSONB, nullable=True)