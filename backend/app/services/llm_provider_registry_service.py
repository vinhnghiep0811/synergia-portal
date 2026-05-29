from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.llm_provider_option import LLMProviderOption
from app.models.user import User

DEFAULT_LLM_PROVIDERS = ["gemini", "deepseek", "ollama"]


class LLMProviderRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def normalize_provider_name(raw_name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9_-]+", "-", (raw_name or "").strip().lower())
        return cleaned.strip("-")

    def list_provider_names(self) -> list[str]:
        rows = self.db.query(LLMProviderOption).order_by(LLMProviderOption.id.asc()).all()
        providers = [row.name for row in rows]
        if not providers:
            providers = DEFAULT_LLM_PROVIDERS.copy()

        normalized: list[str] = []
        seen: set[str] = set()
        for name in providers:
            if name in seen:
                continue
            normalized.append(name)
            seen.add(name)

        if "ollama" not in seen:
            normalized.append("ollama")

        return normalized

    def list_providers(self) -> list[dict]:
        names = self.list_provider_names()
        items: list[dict] = []
        for name in names:
            items.append(
                {
                    "name": name,
                    "is_fallback": name == "ollama",
                    "is_locked": name == "ollama",
                }
            )
        return items

    def add_provider(self, raw_name: str, actor_user: User) -> list[dict]:
        name = self.normalize_provider_name(raw_name)
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider name is required.",
            )
        if len(name) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider name must be 50 characters or fewer.",
            )

        existing_rows = self.db.query(LLMProviderOption).all()
        if not existing_rows:
            for default_name in DEFAULT_LLM_PROVIDERS:
                self.db.add(LLMProviderOption(name=default_name, created_by_user_id=actor_user.id))
            self.db.flush()

        existing = self.db.query(LLMProviderOption).filter(LLMProviderOption.name == name).first()
        if existing is None:
            self.db.add(LLMProviderOption(name=name, created_by_user_id=actor_user.id))
            self.db.commit()
        else:
            self.db.commit()

        return self.list_providers()

    def remove_provider(self, raw_name: str) -> list[dict]:
        name = self.normalize_provider_name(raw_name)
        if name == "ollama":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ollama is the required fallback provider and cannot be removed.",
            )

        row = self.db.query(LLMProviderOption).filter(LLMProviderOption.name == name).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider '{name}' was not found.",
            )

        self.db.delete(row)
        self.db.commit()
        return self.list_providers()

    def ensure_provider_allowed(self, provider_name: str) -> None:
        allowed = set(self.list_provider_names())
        if provider_name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_name}' is not in the provider list. "
                    "Please add it in admin configuration first."
                ),
            )
