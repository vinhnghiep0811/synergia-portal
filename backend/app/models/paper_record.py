from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class PaperRecord(Base):
    __tablename__ = "paper_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    canonical_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    uploader_id = Column(String(255), nullable=True)

    original_filename = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=False)

    file_size_bytes = Column(BigInteger, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)

    upload_source = Column(String(30), nullable=False, default="portal", server_default="portal")
    status = Column(String(30), nullable=False, default="pending", server_default="pending")

    parse_status = Column(String(30), nullable=True)
    parse_error = Column(Text, nullable=True)

    extracted_text_preview = Column(Text, nullable=True)
    detected_doi = Column(String(255), nullable=True)
    detected_title = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    canonical_document = relationship("CanonicalDocument")
    publish_versions = relationship("PublishVersion", back_populates="paper_record")