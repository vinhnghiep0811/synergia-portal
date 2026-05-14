from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.activity import (
    ActivityActorType,
    ActivityEventType,
    ActivityObjectType,
    ActivityStatus,
)
from app.core.config import (
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_MODEL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from app.models.admin_system_config import AdminSystemConfig
from app.models.user import User
from app.schemas.admin import AdminConfigResponse, AdminConfigUpdateRequest
from app.services.activity_log_service import ActivityLogService


class AdminConfigService:
    def __init__(self, db: Session):
        self.db = db
        self.activity_service = ActivityLogService(db)

    def get_configuration(self) -> AdminConfigResponse:
        config = self._get_config()
        if config is None:
            defaults = self._defaults()
            return AdminConfigResponse(
                llm_provider=defaults["llm_provider"],
                llm_model=defaults["llm_model"],
                embedding_model=defaults["embedding_model"],
                metadata_match_threshold=defaults["metadata_match_threshold"],
                pipeline_retry_limit=defaults["pipeline_retry_limit"],
                pipeline_timeout_seconds=defaults["pipeline_timeout_seconds"],
                telegram_enabled=defaults["telegram_enabled"],
                telegram_chat_id=defaults["telegram_chat_id"],
                semantic_scholar_api_key_masked=defaults["semantic_scholar_api_key_masked"],
                telegram_bot_token_masked=defaults["telegram_bot_token_masked"],
                has_semantic_scholar_api_key=defaults["has_semantic_scholar_api_key"],
                has_telegram_bot_token=defaults["has_telegram_bot_token"],
                source="env_default",
                updated_at=None,
                updated_by=None,
            )

        return self._to_response(config, source="database")

    def update_configuration(
        self,
        payload: AdminConfigUpdateRequest,
        actor_user: User,
    ) -> AdminConfigResponse:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return self.get_configuration()

        config = self._get_or_create_config()
        updated_fields: list[str] = []
        secret_fields_changed: list[str] = []

        for field_name, raw_value in data.items():
            value = raw_value
            if isinstance(value, str):
                value = value.strip()

            if field_name in {"semantic_scholar_api_key", "telegram_bot_token"} and value:
                secret_fields_changed.append(field_name)

            if field_name == "llm_provider" and isinstance(value, str):
                value = value.lower()

            setattr(config, field_name, value)
            updated_fields.append(field_name)

        if config.telegram_enabled and (not config.telegram_bot_token or not config.telegram_chat_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_bot_token and telegram_chat_id are required when Telegram is enabled.",
            )

        config.updated_by_user_id = actor_user.id
        self.db.add(config)
        self.db.flush()

        self.activity_service.log(
            actor_type=ActivityActorType.ADMIN,
            actor_user_id=actor_user.id,
            event_type=ActivityEventType.ADMIN_SETTING_UPDATED,
            object_type=ActivityObjectType.SYSTEM_CONFIG,
            object_id=uuid4(),
            status=ActivityStatus.SUCCESS,
            message="Admin updated system configuration",
            metadata_json={
                "updated_fields": updated_fields,
                "llm_provider": config.llm_provider,
                "llm_model": config.llm_model,
                "embedding_model": config.embedding_model,
                "metadata_match_threshold": config.metadata_match_threshold,
                "pipeline_retry_limit": config.pipeline_retry_limit,
                "pipeline_timeout_seconds": config.pipeline_timeout_seconds,
                "telegram_enabled": config.telegram_enabled,
            },
        )

        if secret_fields_changed:
            self.activity_service.log(
                actor_type=ActivityActorType.ADMIN,
                actor_user_id=actor_user.id,
                event_type=ActivityEventType.ADMIN_API_KEY_UPDATED,
                object_type=ActivityObjectType.SYSTEM_CONFIG,
                object_id=uuid4(),
                status=ActivityStatus.INFO,
                message="Admin updated secured credentials",
                metadata_json={"updated_secrets": secret_fields_changed},
            )

        self.db.commit()
        self.db.refresh(config)
        return self._to_response(config, source="database")

    def _get_config(self) -> AdminSystemConfig | None:
        return self.db.query(AdminSystemConfig).order_by(AdminSystemConfig.id.asc()).first()

    def _get_or_create_config(self) -> AdminSystemConfig:
        config = self._get_config()
        if config:
            return config

        defaults = self._defaults()
        config = AdminSystemConfig(
            semantic_scholar_api_key=None,
            llm_provider=defaults["llm_provider"],
            llm_model=defaults["llm_model"],
            embedding_model=defaults["embedding_model"],
            metadata_match_threshold=defaults["metadata_match_threshold"],
            pipeline_retry_limit=defaults["pipeline_retry_limit"],
            pipeline_timeout_seconds=defaults["pipeline_timeout_seconds"],
            telegram_enabled=defaults["telegram_enabled"],
            telegram_bot_token=TELEGRAM_BOT_TOKEN or None,
            telegram_chat_id=defaults["telegram_chat_id"],
        )
        self.db.add(config)
        self.db.flush()
        return config

    def _to_response(self, config: AdminSystemConfig, source: str) -> AdminConfigResponse:
        updated_by = None
        if config.updated_by_user_id:
            user = self.db.query(User).filter(User.id == config.updated_by_user_id).first()
            if user:
                updated_by = user.email

        return AdminConfigResponse(
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            embedding_model=config.embedding_model,
            metadata_match_threshold=float(config.metadata_match_threshold),
            pipeline_retry_limit=config.pipeline_retry_limit,
            pipeline_timeout_seconds=config.pipeline_timeout_seconds,
            telegram_enabled=config.telegram_enabled,
            telegram_chat_id=config.telegram_chat_id,
            semantic_scholar_api_key_masked=self._mask_secret(config.semantic_scholar_api_key),
            telegram_bot_token_masked=self._mask_secret(config.telegram_bot_token),
            has_semantic_scholar_api_key=bool(config.semantic_scholar_api_key),
            has_telegram_bot_token=bool(config.telegram_bot_token),
            source=source,
            updated_at=config.updated_at,
            updated_by=updated_by,
        )

    @staticmethod
    def _mask_secret(secret: str | None) -> str | None:
        if not secret:
            return None
        if len(secret) <= 8:
            return "*" * len(secret)
        return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"

    @staticmethod
    def _defaults() -> dict[str, object]:
        llm_provider = (LLM_PROVIDER or "gemini").lower()
        llm_model = GEMINI_MODEL if llm_provider == "gemini" else OLLAMA_MODEL
        telegram_enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

        return {
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "metadata_match_threshold": 0.7,
            "pipeline_retry_limit": 3,
            "pipeline_timeout_seconds": 300,
            "telegram_enabled": telegram_enabled,
            "telegram_chat_id": TELEGRAM_CHAT_ID or None,
            "semantic_scholar_api_key_masked": None,
            "telegram_bot_token_masked": AdminConfigService._mask_secret(TELEGRAM_BOT_TOKEN),
            "has_semantic_scholar_api_key": False,
            "has_telegram_bot_token": bool(TELEGRAM_BOT_TOKEN),
        }
