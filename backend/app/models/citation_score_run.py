import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CitationScoreRun(Base):
    __tablename__ = "citation_score_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    algorithm_version = Column(String(50), nullable=False, index=True)
    weights_json = Column(JSONB, nullable=False)
    status = Column(
        String(30),
        nullable=False,
        default="running",
        server_default="running",
        index=True,
    )

    processed_mentions = Column(Integer, nullable=False, default=0, server_default="0")
    processed_edges = Column(Integer, nullable=False, default=0, server_default="0")

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    error_log = Column(Text, nullable=True)

    mentions = relationship(
        "CitationMention",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    edges = relationship(
        "CitationEdge",
        back_populates="run",
        cascade="all, delete-orphan",
    )
