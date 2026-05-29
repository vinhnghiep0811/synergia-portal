from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class LLMProviderConfig(Base):
    __tablename__ = "llm_provider_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(50), nullable=False, unique=True)
    base_url = Column(Text, nullable=True)
    model_name = Column(String(255), nullable=True)
    extra_params = Column(JSONB, nullable=True)

    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
