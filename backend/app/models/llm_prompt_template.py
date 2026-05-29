from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class LLMPromptTemplate(Base):
    __tablename__ = "llm_prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(120), nullable=False, unique=True)
    prompt_text = Column(Text, nullable=False)

    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
