from __future__ import annotations

import json
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.activity import (
    ActivityActorType,
    ActivityEventType,
    ActivityObjectType,
    ActivityStatus,
)
from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from app.models.admin_system_config import AdminSystemConfig
from app.models.llm_provider_api_key import LLMProviderApiKey
from app.models.user import User
from app.schemas.admin import (
    AdminConfigResponse,
    AdminConfigUpdateRequest,
    ConfigValidateRequest,
    ConfigValidateResponse,
    ServiceValidationResult,
)
from app.services.activity_log_service import ActivityLogService
from app.services.embedding_service import EMBEDDING_DIM, EmbeddingService
from app.services.llm_provider_registry_service import LLMProviderRegistryService
from app.services.runtime_config_service import RuntimeConfigService


class AdminConfigService:
    def __init__(self, db: Session):
        self.db = db
        self.activity_service = ActivityLogService(db)
        self.provider_registry = LLMProviderRegistryService(db)

    @staticmethod
    def _normalize_provider_name(value: str | None) -> str:
        normalized = (value or "").strip().lower()
        return normalized or "gemini"

    def _get_provider_api_key(self, provider: str) -> str | None:
        normalized = self._normalize_provider_name(provider)
        row = (
            self.db.query(LLMProviderApiKey)
            .filter(LLMProviderApiKey.provider_name == normalized)
            .first()
        )
        if not row:
            return None
        value = (row.api_key or "").strip()
        return value or None

    def _resolve_llm_api_key(self, provider: str, override_key: str | None = None) -> str | None:
        if override_key:
            return override_key
        stored_key = self._get_provider_api_key(provider)
        if stored_key:
            return stored_key
        normalized = self._normalize_provider_name(provider)
        if normalized == "gemini":
            return GEMINI_API_KEY or None
        return None

    def _upsert_llm_api_key(self, provider: str, api_key: str, actor_user: User) -> None:
        normalized = self._normalize_provider_name(provider)
        row = (
            self.db.query(LLMProviderApiKey)
            .filter(LLMProviderApiKey.provider_name == normalized)
            .first()
        )
        if row:
            row.api_key = api_key
            row.updated_by_user_id = actor_user.id
            return

        self.db.add(
            LLMProviderApiKey(
                provider_name=normalized,
                api_key=api_key,
                updated_by_user_id=actor_user.id,
            )
        )

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
                llm_api_key_masked=defaults["llm_api_key_masked"],
                semantic_scholar_api_key_masked=defaults["semantic_scholar_api_key_masked"],
                telegram_bot_token_masked=defaults["telegram_bot_token_masked"],
                has_llm_api_key=defaults["has_llm_api_key"],
                has_semantic_scholar_api_key=defaults["has_semantic_scholar_api_key"],
                has_telegram_bot_token=defaults["has_telegram_bot_token"],
                source="env_default",
                updated_at=None,
                updated_by=None,
            )

        return self._to_response(config, source="database")

    def validate_services(self, payload: ConfigValidateRequest) -> ConfigValidateResponse:
        """Validate individual service connections without saving to database."""
        # Build a temporary config object for validation
        existing_config = self._get_config()
        defaults = RuntimeConfigService.get(self.db)

        def normalize_text(value: object) -> str | None:
            if isinstance(value, str):
                stripped = value.strip()
                return stripped or None
            return None if value is None else str(value)

        provider_value = (
            normalize_text(payload.llm_provider)
            or (existing_config.llm_provider if existing_config else defaults.llm_provider)
        )
        provider_value = self._normalize_provider_name(provider_value)
        self.provider_registry.ensure_provider_allowed(provider_value)

        llm_model_value = normalize_text(payload.llm_model)
        if not llm_model_value:
            existing_provider = (
                self._normalize_provider_name(existing_config.llm_provider)
                if existing_config
                else None
            )
            if existing_config and provider_value == existing_provider:
                llm_model_value = normalize_text(existing_config.llm_model)
        if not llm_model_value:
            llm_model_value = GEMINI_MODEL if provider_value != "ollama" else OLLAMA_MODEL

        llm_api_key_value = normalize_text(payload.llm_api_key)
        resolved_llm_api_key = self._resolve_llm_api_key(provider_value, llm_api_key_value)

        embedding_model_value = normalize_text(payload.embedding_model)
        if not embedding_model_value:
            embedding_model_value = (
                normalize_text(existing_config.embedding_model)
                if existing_config
                else None
            ) or defaults.embedding_model

        semantic_key_value = normalize_text(payload.semantic_scholar_api_key)
        if not semantic_key_value:
            semantic_key_value = (
                normalize_text(existing_config.semantic_scholar_api_key)
                if existing_config
                else None
            ) or defaults.semantic_scholar_api_key

        telegram_bot_token_value = normalize_text(payload.telegram_bot_token) or (
            normalize_text(existing_config.telegram_bot_token)
            if existing_config
            else None
        )
        telegram_chat_id_value = normalize_text(payload.telegram_chat_id) or (
            normalize_text(existing_config.telegram_chat_id)
            if existing_config
            else None
        )

        temp = AdminSystemConfig(
            llm_provider=provider_value,
            llm_model=llm_model_value,
            embedding_model=embedding_model_value,
            semantic_scholar_api_key=semantic_key_value,
            telegram_bot_token=telegram_bot_token_value,
            telegram_chat_id=telegram_chat_id_value,
            telegram_enabled=True,  # force enabled for validation
            pipeline_timeout_seconds=payload.pipeline_timeout_seconds
            or (existing_config.pipeline_timeout_seconds if existing_config else 300),
        )

        services_to_validate = []
        if payload.service == "all":
            services_to_validate = ["llm", "semantic_scholar", "embedding", "telegram"]
        else:
            services_to_validate = [payload.service]

        results: list[ServiceValidationResult] = []
        for svc in services_to_validate:
            result = self._validate_single_service(svc, temp, resolved_llm_api_key)
            results.append(result)

        all_ok = all(r.ok for r in results)
        return ConfigValidateResponse(results=results, all_ok=all_ok)

    def _validate_single_service(
        self,
        service: str,
        config: AdminSystemConfig,
        llm_api_key: str | None = None,
    ) -> ServiceValidationResult:
        """Validate a single service and return a structured result instead of raising."""
        try:
            if service == "llm":
                self._validate_llm_configuration(config, llm_api_key)
                return ServiceValidationResult(
                    service="llm",
                    ok=True,
                    message=f"LLM ({config.llm_provider}/{config.llm_model}) connected successfully.",
                )
            elif service == "semantic_scholar":
                self._validate_semantic_scholar_configuration(config)
                return ServiceValidationResult(
                    service="semantic_scholar",
                    ok=True,
                    message="Semantic Scholar API key is valid.",
                )
            elif service == "embedding":
                self._validate_embedding_configuration(config)
                return ServiceValidationResult(
                    service="embedding",
                    ok=True,
                    message=f"Embedding model '{config.embedding_model}' validated successfully.",
                )
            elif service == "telegram":
                # Validate only if we have token and chat_id
                token = (config.telegram_bot_token or "").strip()
                chat_id = (config.telegram_chat_id or "").strip()
                if not token or not chat_id:
                    return ServiceValidationResult(
                        service="telegram",
                        ok=False,
                        message="Telegram bot_token and chat_id are both required.",
                        detail="Please provide both telegram_bot_token and telegram_chat_id.",
                    )
                self._validate_telegram_configuration(config)
                return ServiceValidationResult(
                    service="telegram",
                    ok=True,
                    message="Telegram bot and chat validated successfully.",
                )
            else:
                return ServiceValidationResult(
                    service=service,
                    ok=False,
                    message=f"Unknown service: {service}",
                )
        except HTTPException as exc:
            return ServiceValidationResult(
                service=service,
                ok=False,
                message=str(exc.detail),
                detail=f"HTTP {exc.status_code}",
            )
        except Exception as exc:
            return ServiceValidationResult(
                service=service,
                ok=False,
                message=f"Unexpected error: {exc}",
            )

    def update_configuration(
        self,
        payload: AdminConfigUpdateRequest,
        actor_user: User,
    ) -> AdminConfigResponse:
        if payload.use_default_settings is True:
            return self._activate_default_settings(actor_user)

        data = payload.model_dump(exclude_unset=True)
        data.pop("use_default_settings", None)

        defaults = RuntimeConfigService.get()
        default_telegram_enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

        def normalize_text(value: object) -> str | None:
            if isinstance(value, str):
                stripped = value.strip()
                return stripped or None
            return None if value is None else str(value)

        provider_value = normalize_text(data.get("llm_provider")) or defaults.llm_provider
        provider_value = self._normalize_provider_name(provider_value)
        self.provider_registry.ensure_provider_allowed(provider_value)

        llm_model_value = normalize_text(data.get("llm_model"))
        if not llm_model_value:
            llm_model_value = (
                defaults.llm_model
                if provider_value == defaults.llm_provider
                else (GEMINI_MODEL if provider_value != "ollama" else OLLAMA_MODEL)
            )

        llm_api_key_value = normalize_text(data.get("llm_api_key"))
        resolved_llm_api_key = self._resolve_llm_api_key(provider_value, llm_api_key_value)
        semantic_key_value = normalize_text(data.get("semantic_scholar_api_key")) or defaults.semantic_scholar_api_key
        embedding_model_value = normalize_text(data.get("embedding_model")) or defaults.embedding_model

        metadata_match_threshold = (
            data.get("metadata_match_threshold")
            if data.get("metadata_match_threshold") is not None
            else defaults.metadata_match_threshold
        )
        pipeline_retry_limit = (
            data.get("pipeline_retry_limit")
            if data.get("pipeline_retry_limit") is not None
            else defaults.pipeline_retry_limit
        )
        pipeline_timeout_seconds = (
            data.get("pipeline_timeout_seconds")
            if data.get("pipeline_timeout_seconds") is not None
            else defaults.pipeline_timeout_seconds
        )

        telegram_enabled = (
            data.get("telegram_enabled")
            if data.get("telegram_enabled") is not None
            else default_telegram_enabled
        )
        telegram_bot_token = normalize_text(data.get("telegram_bot_token")) or (TELEGRAM_BOT_TOKEN or None)
        telegram_chat_id = normalize_text(data.get("telegram_chat_id")) or (TELEGRAM_CHAT_ID or None)

        config = self._get_or_create_config()
        effective_values = {
            "llm_provider": provider_value,
            "llm_model": llm_model_value,
            "embedding_model": embedding_model_value,
            "metadata_match_threshold": metadata_match_threshold,
            "pipeline_retry_limit": pipeline_retry_limit,
            "pipeline_timeout_seconds": pipeline_timeout_seconds,
            "semantic_scholar_api_key": semantic_key_value,
            "telegram_enabled": bool(telegram_enabled),
            "telegram_bot_token": telegram_bot_token,
            "telegram_chat_id": telegram_chat_id,
        }

        updated_fields: list[str] = []
        secret_fields_changed: list[str] = []
        for field_name, value in effective_values.items():
            setattr(config, field_name, value)
            updated_fields.append(field_name)

        if normalize_text(data.get("semantic_scholar_api_key")):
            secret_fields_changed.append("semantic_scholar_api_key")
        if normalize_text(data.get("telegram_bot_token")):
            secret_fields_changed.append("telegram_bot_token")
        if normalize_text(data.get("llm_api_key")):
            secret_fields_changed.append("llm_api_key")

        if config.telegram_enabled and (not config.telegram_bot_token or not config.telegram_chat_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_bot_token and telegram_chat_id are required when Telegram is enabled.",
            )

        self._validate_custom_configuration(config, resolved_llm_api_key)

        if llm_api_key_value:
            self._upsert_llm_api_key(provider_value, llm_api_key_value, actor_user)

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

    def _activate_default_settings(self, actor_user: User) -> AdminConfigResponse:
        config = self._get_config()
        if config is not None:
            self.db.delete(config)
            self.db.flush()

        self.activity_service.log(
            actor_type=ActivityActorType.ADMIN,
            actor_user_id=actor_user.id,
            event_type=ActivityEventType.ADMIN_SETTING_UPDATED,
            object_type=ActivityObjectType.SYSTEM_CONFIG,
            object_id=uuid4(),
            status=ActivityStatus.SUCCESS,
            message="Admin switched system configuration to default settings",
            metadata_json={
                "mode": "env_default",
                "updated_fields": ["use_default_settings"],
            },
        )

        self.db.commit()
        return self.get_configuration()

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

        llm_api_key = self._resolve_llm_api_key(config.llm_provider)

        return AdminConfigResponse(
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            embedding_model=config.embedding_model,
            metadata_match_threshold=float(config.metadata_match_threshold),
            pipeline_retry_limit=config.pipeline_retry_limit,
            pipeline_timeout_seconds=config.pipeline_timeout_seconds,
            telegram_enabled=config.telegram_enabled,
            telegram_chat_id=config.telegram_chat_id,
            llm_api_key_masked=self._mask_secret(llm_api_key),
            semantic_scholar_api_key_masked=self._mask_secret(config.semantic_scholar_api_key),
            telegram_bot_token_masked=self._mask_secret(config.telegram_bot_token),
            has_llm_api_key=bool(llm_api_key),
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

    def _defaults(self) -> dict[str, object]:
        runtime_defaults = RuntimeConfigService.get(self.db)
        telegram_enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

        return {
            "llm_provider": runtime_defaults.llm_provider,
            "llm_model": runtime_defaults.llm_model,
            "embedding_model": runtime_defaults.embedding_model,
            "metadata_match_threshold": runtime_defaults.metadata_match_threshold,
            "pipeline_retry_limit": runtime_defaults.pipeline_retry_limit,
            "pipeline_timeout_seconds": runtime_defaults.pipeline_timeout_seconds,
            "telegram_enabled": telegram_enabled,
            "telegram_chat_id": TELEGRAM_CHAT_ID or None,
            "llm_api_key_masked": self._mask_secret(runtime_defaults.llm_api_key),
            "semantic_scholar_api_key_masked": AdminConfigService._mask_secret(
                runtime_defaults.semantic_scholar_api_key
            ),
            "telegram_bot_token_masked": AdminConfigService._mask_secret(TELEGRAM_BOT_TOKEN),
            "has_llm_api_key": bool(runtime_defaults.llm_api_key),
            "has_semantic_scholar_api_key": bool(runtime_defaults.semantic_scholar_api_key),
            "has_telegram_bot_token": bool(TELEGRAM_BOT_TOKEN),
        }

    def _request_timeout_seconds(self, config: AdminSystemConfig) -> float:
        timeout_value = int(config.pipeline_timeout_seconds or 300)
        return float(max(5, min(timeout_value, 30)))

    def _validate_custom_configuration(
        self, config: AdminSystemConfig, llm_api_key: str | None = None
    ) -> None:
        self._validate_llm_configuration(config, llm_api_key)
        self._validate_semantic_scholar_configuration(config)
        self._validate_embedding_configuration(config)
        self._validate_telegram_configuration(config)

    def _validate_llm_configuration(
        self, config: AdminSystemConfig, llm_api_key: str | None = None
    ) -> None:
        provider = (config.llm_provider or "").strip().lower() or "gemini"
        model_name = (config.llm_model or "").strip()
        api_key = (llm_api_key or "").strip()

        self.provider_registry.ensure_provider_allowed(provider)
        if not model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="llm_model is required when using custom settings.",
            )

        timeout_seconds = self._request_timeout_seconds(config)
        if provider != "ollama":
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "LLM API key is missing in environment/admin config. "
                        "Choose default settings or configure environment first."
                    ),
                )
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{model_name}:generateContent"
            )
            payload = {
                "contents": [{"parts": [{"text": "Return JSON: {\"ok\": true}"}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 64,
                    "temperature": 0,
                },
            }
            try:
                response = httpx.post(
                    endpoint,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    json=payload,
                    timeout=timeout_seconds,
                )
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unable to reach Gemini API: {exc}",
                ) from exc

            if response.status_code != 200:
                error_preview = response.text[:300]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Gemini validation failed for model '{model_name}' "
                        f"(status={response.status_code}): {error_preview}"
                    ),
                )
            return

        payload = {
            "model": model_name,
            "prompt": "Return JSON: {\"ok\": true}",
            "stream": False,
            "format": "json",
            "options": {"num_predict": 32, "temperature": 0},
        }
        try:
            response = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to reach Ollama endpoint {OLLAMA_BASE_URL}: {exc}",
            ) from exc

        if response.status_code != 200:
            error_preview = response.text[:300]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ollama validation failed for model '{model_name}' "
                    f"(status={response.status_code}): {error_preview}"
                ),
            )

        try:
            response_json = response.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ollama returned invalid JSON during validation.",
            ) from exc

        generated_text = (response_json.get("response") or "").strip()
        if not generated_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ollama returned empty response during validation.",
            )

    def _validate_semantic_scholar_configuration(self, config: AdminSystemConfig) -> None:
        semantic_key = (config.semantic_scholar_api_key or "").strip()
        if not semantic_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "semantic_scholar_api_key is required for custom settings. "
                    "Use default settings to rely on .env."
                ),
            )

        timeout_seconds = self._request_timeout_seconds(config)
        try:
            response = httpx.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": "machine learning", "limit": 1, "fields": "title"},
                headers={"x-api-key": semantic_key},
                timeout=timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to reach Semantic Scholar API: {exc}",
            ) from exc

        if response.status_code in {200, 429}:
            return
        if response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Semantic Scholar API key is invalid or unauthorized.",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Semantic Scholar validation failed "
                f"(status={response.status_code}): {response.text[:300]}"
            ),
        )

    def _validate_embedding_configuration(self, config: AdminSystemConfig) -> None:
        model_name = (config.embedding_model or "").strip()
        if not model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="embedding_model is required for custom settings.",
            )

        try:
            embedding_service = EmbeddingService(model_name=model_name)
            vector = embedding_service.generate_embedding("embedding validation")
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Embedding model validation failed: {exc}",
            ) from exc

        if len(vector) != EMBEDDING_DIM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Embedding model dimension mismatch: expected {EMBEDDING_DIM}, "
                    f"got {len(vector)}."
                ),
            )

    def _validate_telegram_configuration(self, config: AdminSystemConfig) -> None:
        if not config.telegram_enabled:
            return

        token = (config.telegram_bot_token or "").strip()
        chat_id = (config.telegram_chat_id or "").strip()
        if not token or not chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_bot_token and telegram_chat_id are required when Telegram is enabled.",
            )

        timeout_seconds = self._request_timeout_seconds(config)
        get_me_url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            bot_response = httpx.get(get_me_url, timeout=timeout_seconds)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to reach Telegram API: {exc}",
            ) from exc

        if bot_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Telegram bot token validation failed "
                    f"(status={bot_response.status_code}): {bot_response.text[:300]}"
                ),
            )

        try:
            bot_payload = bot_response.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot validation returned invalid JSON.",
            ) from exc

        if not bot_payload.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Telegram bot token invalid: {bot_payload.get('description') or 'Unknown error'}",
            )

        try:
            chat_response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
                timeout=timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to validate Telegram chat_id: {exc}",
            ) from exc

        if chat_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Telegram chat_id validation failed "
                    f"(status={chat_response.status_code}): {chat_response.text[:300]}"
                ),
            )

        try:
            chat_payload = chat_response.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram chat validation returned invalid JSON.",
            ) from exc

        if not chat_payload.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Telegram chat_id invalid: {chat_payload.get('description') or 'Unknown error'}",
            )
