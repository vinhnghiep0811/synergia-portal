from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    canonical_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    section_index = Column(Integer, nullable=False)
    section_name = Column(String(500), nullable=True)
    section_type = Column(String(50), nullable=True)  # intro, method, results, references...

    heading_number = Column(String(50), nullable=True)   # ví dụ: 3, 3.1, 4.2
    heading_level = Column(Integer, nullable=False, default=0)  # 0=document, 1=main, 2=subsection...

    parent_section_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    full_path = Column(Text, nullable=True)

    page_from = Column(Integer, nullable=True)
    page_to = Column(Integer, nullable=True)

    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    canonical_document = relationship("CanonicalDocument", back_populates="document_sections")

    parent_section = relationship(
        "DocumentSection",
        remote_side=[id],
        foreign_keys=[parent_section_id],
        backref="child_sections",
    )