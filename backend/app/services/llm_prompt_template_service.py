from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.llm_prompt_template import LLMPromptTemplate
from app.models.user import User
from app.services.llm.prompt_templates import (
    PROMPT_TEMPLATE_CATALOG,
    DEFAULT_PROMPT_TEMPLATES,
    PROMPT_TEMPLATE_KEY_MIGRATIONS,
)


class LLMPromptTemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _ensure_defaults(self) -> None:
        self._migrate_legacy_keys()
        existing_keys = {
            row[0]
            for row in self.db.query(LLMPromptTemplate.key).all()
        }
        missing_keys = [
            key for key in PROMPT_TEMPLATE_CATALOG.keys()
            if key not in existing_keys
        ]
        if not missing_keys:
            return

        for key in missing_keys:
            self.db.add(
                LLMPromptTemplate(
                    key=key,
                    prompt_text=DEFAULT_PROMPT_TEMPLATES[key],
                )
            )
        self.db.commit()

    def _migrate_legacy_keys(self) -> None:
        if not PROMPT_TEMPLATE_KEY_MIGRATIONS:
            return

        legacy_keys = list(PROMPT_TEMPLATE_KEY_MIGRATIONS.keys())
        legacy_rows = (
            self.db.query(LLMPromptTemplate)
            .filter(LLMPromptTemplate.key.in_(legacy_keys))
            .all()
        )
        if not legacy_rows:
            return

        new_keys = list(PROMPT_TEMPLATE_KEY_MIGRATIONS.values())
        existing_new_keys = {
            row[0]
            for row in self.db.query(LLMPromptTemplate.key)
            .filter(LLMPromptTemplate.key.in_(new_keys))
            .all()
        }

        for row in legacy_rows:
            new_key = PROMPT_TEMPLATE_KEY_MIGRATIONS.get(row.key)
            if not new_key:
                continue
            if new_key in existing_new_keys:
                self.db.delete(row)
                continue
            row.key = new_key
            existing_new_keys.add(new_key)

        self.db.commit()

    def list_templates(self) -> list[dict]:
        self._ensure_defaults()
        keys = list(PROMPT_TEMPLATE_CATALOG.keys())
        rows = (
            self.db.query(LLMPromptTemplate)
            .filter(LLMPromptTemplate.key.in_(keys))
            .all()
        )
        row_map = {row.key: row for row in rows}
        user_ids = [row.updated_by_user_id for row in rows if row.updated_by_user_id]
        email_map = {}
        if user_ids:
            users = self.db.query(User).filter(User.id.in_(user_ids)).all()
            email_map = {user.id: user.email for user in users}

        templates: list[dict] = []
        for key, meta in PROMPT_TEMPLATE_CATALOG.items():
            row = row_map.get(key)
            default_template = DEFAULT_PROMPT_TEMPLATES[key]
            content = row.prompt_text if row else default_template
            is_default = (row is None) or (row.prompt_text.strip() == default_template.strip())

            updated_by = None
            updated_at = None
            if row:
                updated_at = row.updated_at
                if row.updated_by_user_id:
                    updated_by = email_map.get(row.updated_by_user_id)

            templates.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "content": content,
                    "is_default": is_default,
                    "updated_at": updated_at,
                    "updated_by": updated_by,
                }
            )

        return templates

    def get_template_map(self) -> dict[str, str]:
        templates = self.list_templates()
        return {item["key"]: item["content"] for item in templates}

    def update_templates(self, updates: list[dict], actor_user: User) -> list[dict]:
        if not updates:
            return self.list_templates()

        keys = list(PROMPT_TEMPLATE_CATALOG.keys())
        existing = (
            self.db.query(LLMPromptTemplate)
            .filter(LLMPromptTemplate.key.in_(keys))
            .all()
        )
        row_map = {row.key: row for row in existing}

        for update in updates:
            if hasattr(update, "key"):
                key = (update.key or "").strip()
                content = update.content
            else:
                key = (update.get("key") or "").strip()
                content = update.get("content")

            if key not in PROMPT_TEMPLATE_CATALOG:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown prompt key: {key}",
                )

            if not isinstance(content, str) or not content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Prompt content for '{key}' must not be empty.",
                )

            row = row_map.get(key)
            if row is None:
                row = LLMPromptTemplate(
                    key=key,
                    prompt_text=content,
                    updated_by_user_id=actor_user.id,
                )
                self.db.add(row)
                row_map[key] = row
            else:
                row.prompt_text = content
                row.updated_by_user_id = actor_user.id

        self.db.commit()
        return self.list_templates()
