from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AdminConfigUpdateRequest(BaseModel):
    semantic_scholar_api_key: str | None = Field(
        default=None,
        min_length=8,
        description="Optional. Leave empty to keep existing key.",
    )
    llm_provider: str | None = Field(default=None, pattern="^(gemini|ollama)$")
    llm_model: str | None = Field(default=None, min_length=1, max_length=255)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=255)
    metadata_match_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    pipeline_retry_limit: int | None = Field(default=None, ge=0, le=10)
    pipeline_timeout_seconds: int | None = Field(default=None, ge=10, le=3600)
    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = Field(default=None, min_length=8)
    telegram_chat_id: str | None = Field(default=None, min_length=2, max_length=255)

    @model_validator(mode="after")
    def validate_telegram_dependency(self):
        if self.telegram_enabled is True:
            token_missing = self.telegram_bot_token is None
            chat_missing = self.telegram_chat_id is None
            if token_missing and chat_missing:
                raise ValueError(
                    "telegram_bot_token or telegram_chat_id is required when telegram_enabled=true"
                )
        return self


class AdminConfigResponse(BaseModel):
    llm_provider: str
    llm_model: str | None
    embedding_model: str | None
    metadata_match_threshold: float
    pipeline_retry_limit: int
    pipeline_timeout_seconds: int
    telegram_enabled: bool
    telegram_chat_id: str | None
    semantic_scholar_api_key_masked: str | None
    telegram_bot_token_masked: str | None
    has_semantic_scholar_api_key: bool
    has_telegram_bot_token: bool
    source: str
    updated_at: datetime | None
    updated_by: str | None


class ProcessingLogSummaryItem(BaseModel):
    event_type: str
    count: int


class SearchSampleItem(BaseModel):
    event_type: str
    created_at: datetime
    actor_email: str | None
    query: str
    result_count: int
    top_k_or_limit: int


class AdminEvaluationSummary(BaseModel):
    total_papers: int
    draft_papers: int
    published_papers: int
    jobs_processing: int
    jobs_failed: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    avg_pipeline_seconds: float | None


class AdminEvaluationReportResponse(BaseModel):
    generated_at: datetime
    window_days: int
    summary: AdminEvaluationSummary
    processing_errors: list[ProcessingLogSummaryItem]
    search_samples: list[SearchSampleItem]
    processing_status: dict[str, int]
    publication_status: dict[str, int]
    extra_metrics: dict[str, Any]
