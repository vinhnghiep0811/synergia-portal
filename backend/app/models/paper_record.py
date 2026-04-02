from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func
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

    duplicate_of_paper_id = Column(
        UUID(as_uuid=True),
        ForeignKey("paper_records.id", ondelete="SET NULL"),
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
    # status = Column(String(30), nullable=False, default="uploaded", server_default="uploaded")
    processing_status = Column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    # 2) Đang ở bước nào trong pipeline
    processing_stage = Column(
        String(30),
        nullable=True,
        index=True,
    )

    # 3) Trạng thái nghiệp vụ công bố
    publication_status = Column(
        String(30),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    # parse_status = Column(String(30), nullable=True)
    processing_error = Column(Text, nullable=True)

    extracted_text_preview = Column(Text, nullable=True)
    detected_doi = Column(String(255), nullable=True)
    detected_fingerprint = Column(String(255), nullable=True)
    detected_title = Column(Text, nullable=True)

    is_duplicate = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    canonical_document = relationship("CanonicalDocument", back_populates="papers")
    duplicate_of_paper = relationship(
        "PaperRecord",
        remote_side=[id],
        foreign_keys=[duplicate_of_paper_id],
    )
    publish_versions = relationship("PublishVersion", back_populates="paper_record")