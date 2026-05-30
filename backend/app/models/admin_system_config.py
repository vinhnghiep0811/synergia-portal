from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AdminSystemConfig(Base):
    __tablename__ = "admin_system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    semantic_scholar_api_key = Column(Text, nullable=True)
    llm_provider = Column(String(50), nullable=False, default="openrouter", server_default="openrouter")
    llm_model = Column(String(255), nullable=True)
    embedding_model = Column(String(255), nullable=True)

    metadata_match_threshold = Column(
        Float,
        nullable=False,
        default=0.7,
        server_default="0.7",
    )
    pipeline_retry_limit = Column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )
    pipeline_timeout_seconds = Column(
        Integer,
        nullable=False,
        default=300,
        server_default="300",
    )

    telegram_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    telegram_bot_token = Column(Text, nullable=True)
    telegram_chat_id = Column(String(255), nullable=True)

    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
