from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import GEMINI_MODEL, LLM_PROVIDER, OLLAMA_MODEL
from app.models.admin_system_config import AdminSystemConfig

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_METADATA_MATCH_THRESHOLD = 0.7
DEFAULT_PIPELINE_RETRY_LIMIT = 3
DEFAULT_PIPELINE_TIMEOUT_SECONDS = 300
DEFAULT_SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()


@dataclass(frozen=True)
class RuntimeSystemConfig:
    semantic_scholar_api_key: str | None
    llm_provider: str
    llm_model: str
    embedding_model: str
    metadata_match_threshold: float
    pipeline_retry_limit: int
    pipeline_timeout_seconds: int


def _normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in {"gemini", "ollama"}:
        return normalized
    return "gemini"


def _default_llm_model(provider: str) -> str:
    return GEMINI_MODEL if provider == "gemini" else OLLAMA_MODEL


class RuntimeConfigService:
    @staticmethod
    def get(db: Session | None = None) -> RuntimeSystemConfig:
        default_provider = _normalize_provider(LLM_PROVIDER)
        defaults = RuntimeSystemConfig(
            semantic_scholar_api_key=DEFAULT_SEMANTIC_SCHOLAR_API_KEY or None,
            llm_provider=default_provider,
            llm_model=_default_llm_model(default_provider),
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
            return defaults

        llm_provider = _normalize_provider(config.llm_provider or defaults.llm_provider)
        llm_model = (config.llm_model or "").strip() or _default_llm_model(llm_provider)
        embedding_model = (config.embedding_model or "").strip() or defaults.embedding_model

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
            llm_provider=llm_provider,
            llm_model=llm_model,
            embedding_model=embedding_model,
            metadata_match_threshold=metadata_match_threshold,
            pipeline_retry_limit=pipeline_retry_limit,
            pipeline_timeout_seconds=pipeline_timeout_seconds,
        )
