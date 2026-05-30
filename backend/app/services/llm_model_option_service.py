from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.llm_provider_option import LLMProviderOption


class LLMModelOptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _normalize_name(name: str) -> str:
        return (name or "").strip()

    def list_models(self) -> list[LLMProviderOption]:
        return (
            self.db.query(LLMProviderOption)
            .order_by(LLMProviderOption.name.asc())
            .all()
        )

    def create_model(self, name: str, actor_user_id: UUID | None = None) -> LLMProviderOption:
        normalized = self._normalize_name(name)
        if not normalized:
            raise ValueError("Model name cannot be empty.")

        existing = (
            self.db.query(LLMProviderOption)
            .filter(LLMProviderOption.name.ilike(normalized))
            .first()
        )
        if existing:
            raise ValueError("Model name already exists.")

        row = LLMProviderOption(
            name=normalized,
            created_by_user_id=actor_user_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_model(self, model_id: int, name: str) -> LLMProviderOption:
        normalized = self._normalize_name(name)
        if not normalized:
            raise ValueError("Model name cannot be empty.")

        row = self.db.query(LLMProviderOption).filter(LLMProviderOption.id == model_id).first()
        if not row:
            raise ValueError("Model option not found.")

        existing = (
            self.db.query(LLMProviderOption)
            .filter(LLMProviderOption.id != model_id)
            .filter(LLMProviderOption.name.ilike(normalized))
            .first()
        )
        if existing:
            raise ValueError("Model name already exists.")

        row.name = normalized
        self.db.add(row)
        self.db.flush()
        return row

    def delete_model(self, model_id: int) -> None:
        row = self.db.query(LLMProviderOption).filter(LLMProviderOption.id == model_id).first()
        if not row:
            raise ValueError("Model option not found.")
        self.db.delete(row)
        self.db.flush()
