from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)
from app.models.admin_system_config import AdminSystemConfig
from app.models.llm_provider_api_key import LLMProviderApiKey
from app.models.llm_provider_config import LLMProviderConfig

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_METADATA_MATCH_THRESHOLD = 0.7
DEFAULT_PIPELINE_RETRY_LIMIT = 3
DEFAULT_PIPELINE_TIMEOUT_SECONDS = 300
DEFAULT_SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
ALLOWED_LLM_PROVIDERS = {"openrouter", "ollama"}
PRIMARY_PROVIDER = "openrouter"


@dataclass(frozen=True)
class RuntimeSystemConfig:
    semantic_scholar_api_key: str | None
    llm_api_key: str | None
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_extra_params: dict[str, Any] | None
    embedding_model: str
    metadata_match_threshold: float
    pipeline_retry_limit: int
    pipeline_timeout_seconds: int


def _normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in {"gemini", "deepseek", "primary"}:
        return PRIMARY_PROVIDER
    if normalized in {"secondary"}:
        return "ollama"
    if not normalized:
        return PRIMARY_PROVIDER
    return normalized if normalized in ALLOWED_LLM_PROVIDERS else PRIMARY_PROVIDER


def _default_llm_model(provider: str) -> str:
    if provider == "ollama":
        return OLLAMA_MODEL
    return OPENROUTER_MODEL


def _default_llm_base_url(provider: str) -> str | None:
    if provider == "ollama":
        return OLLAMA_BASE_URL
    return OPENROUTER_BASE_URL


def _default_llm_api_key() -> str | None:
    return OPENROUTER_API_KEY or None


def _get_primary_api_key(db: Session) -> str | None:
    row = (
        db.query(LLMProviderApiKey)
        .filter(LLMProviderApiKey.provider_name == PRIMARY_PROVIDER)
        .first()
    )
    if not row:
        return None
    value = (row.api_key or "").strip()
    return value or None


def _get_provider_config(db: Session, provider: str) -> LLMProviderConfig | None:
    normalized = _normalize_provider(provider)
    if normalized != PRIMARY_PROVIDER:
        return None
    return (
        db.query(LLMProviderConfig)
        .filter(LLMProviderConfig.provider_name == PRIMARY_PROVIDER)
        .first()
    )


class RuntimeConfigService:
    @staticmethod
    def get(db: Session | None = None) -> RuntimeSystemConfig:
        default_provider = _normalize_provider(LLM_PROVIDER)
        defaults = RuntimeSystemConfig(
            semantic_scholar_api_key=DEFAULT_SEMANTIC_SCHOLAR_API_KEY or None,
            llm_api_key=_default_llm_api_key(),
            llm_provider=default_provider,
            llm_model=_default_llm_model(default_provider),
            llm_base_url=_default_llm_base_url(default_provider),
            llm_extra_params=None,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            metadata_match_threshold=DEFAULT_METADATA_MATCH_THRESHOLD,
            pipeline_retry_limit=DEFAULT_PIPELINE_RETRY_LIMIT,
            pipeline_timeout_seconds=DEFAULT_PIPELINE_TIMEOUT_SECONDS,
        )

        if db is None:
            return defaults

        config = (
            db.query(AdminSystemConfig)
            .order_by(AdminSystemConfig.id.asc())
            .first()
        )
        if config is None:
            provider_key = _get_primary_api_key(db)
            llm_api_key = provider_key or _default_llm_api_key()
            provider_config = _get_provider_config(db, defaults.llm_provider)
            llm_base_url = _default_llm_base_url(defaults.llm_provider)
            llm_extra_params = (
                provider_config.extra_params
                if provider_config and isinstance(provider_config.extra_params, dict)
                else None
            )
            return RuntimeSystemConfig(
                semantic_scholar_api_key=defaults.semantic_scholar_api_key,
                llm_api_key=llm_api_key,
                llm_provider=defaults.llm_provider,
                llm_model=defaults.llm_model,
                llm_base_url=llm_base_url,
                llm_extra_params=llm_extra_params,
                embedding_model=defaults.embedding_model,
                metadata_match_threshold=defaults.metadata_match_threshold,
                pipeline_retry_limit=defaults.pipeline_retry_limit,
                pipeline_timeout_seconds=defaults.pipeline_timeout_seconds,
            )

        llm_provider = _normalize_provider(config.llm_provider or defaults.llm_provider)
        provider_config = _get_provider_config(db, llm_provider)

        llm_model = (config.llm_model or "").strip()
        if llm_provider == "ollama":
            llm_model = _default_llm_model(llm_provider)
        elif not llm_model:
            llm_model = (
                (provider_config.model_name or "").strip()
                if provider_config and provider_config.model_name
                else _default_llm_model(llm_provider)
            )
        embedding_model = (config.embedding_model or "").strip() or defaults.embedding_model
        provider_key = _get_primary_api_key(db)
        llm_api_key = provider_key or _default_llm_api_key()

        llm_base_url = _default_llm_base_url(llm_provider)
        llm_extra_params = None
        if llm_provider == PRIMARY_PROVIDER and provider_config and isinstance(provider_config.extra_params, dict):
            llm_extra_params = provider_config.extra_params

        if config.metadata_match_threshold is None:
            metadata_match_threshold = defaults.metadata_match_threshold
        else:
            metadata_match_threshold = max(0.0, min(1.0, float(config.metadata_match_threshold)))

        if config.pipeline_retry_limit is None:
            pipeline_retry_limit = defaults.pipeline_retry_limit
        else:
            pipeline_retry_limit = max(0, int(config.pipeline_retry_limit))

        if config.pipeline_timeout_seconds is None:
            pipeline_timeout_seconds = defaults.pipeline_timeout_seconds
        else:
            pipeline_timeout_seconds = max(10, int(config.pipeline_timeout_seconds))

        semantic_scholar_api_key = (
            (config.semantic_scholar_api_key or "").strip()
            or defaults.semantic_scholar_api_key
            or None
        )

        return RuntimeSystemConfig(
            semantic_scholar_api_key=semantic_scholar_api_key,
            llm_api_key=llm_api_key,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            llm_extra_params=llm_extra_params,
            embedding_model=embedding_model,
            metadata_match_threshold=metadata_match_threshold,
            pipeline_retry_limit=pipeline_retry_limit,
            pipeline_timeout_seconds=pipeline_timeout_seconds,
        )
