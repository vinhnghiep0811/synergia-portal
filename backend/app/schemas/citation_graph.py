from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CitationScoreRequest(BaseModel):
    algorithm_version: str | None = Field(default=None, max_length=50)
    source_canonical_ids: list[UUID] | None = None
    force_full_rebuild: bool = False


class CitationScoreEnqueueResponse(BaseModel):
    message: str
    queued_job_id: str
    algorithm_version: str | None = None
    source_canonical_ids: list[UUID] | None = None
    paper_id: UUID | None = None


class CitationQueueJobStatusResponse(BaseModel):
    job_id: str
    status: str
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_excerpt: str | None = None


class CanonicalDocumentCitationSummaryResponse(BaseModel):
    id: UUID
    canonical_key: str
    title: str | None = None
    doi: str | None = None
    publication_year: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CitationScoreRunResponse(BaseModel):
    id: UUID
    algorithm_version: str
    weights_json: dict[str, Any]
    status: str
    processed_mentions: int
    processed_edges: int
    started_at: datetime
    ended_at: datetime | None = None
    error_log: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CitationEdgeResponse(BaseModel):
    id: UUID
    run_id: UUID
    algorithm_version: str
    source_canonical_id: UUID
    target_canonical_id: UUID

    source_document: CanonicalDocumentCitationSummaryResponse | None = None
    target_document: CanonicalDocumentCitationSummaryResponse | None = None

    mention_count: int
    top3_mean_score: Decimal
    frequency_score: Decimal
    diversity_score: Decimal
    intent_edge_score: Decimal
    citation_score: Decimal
    score_band: str | None = None
    evidence_json: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitationEdgeListResponse(BaseModel):
    run: CitationScoreRunResponse
    direction: str
    canonical_document_id: UUID
    items: list[CitationEdgeResponse]


class CitationMentionResponse(BaseModel):
    id: UUID
    run_id: UUID
    source_canonical_id: UUID
    target_canonical_id: UUID | None = None
    source_chunk_id: UUID | None = None
    source_section_id: UUID | None = None

    anchor_text: str | None = None
    context_snippet: str
    page_from: int | None = None
    page_to: int | None = None

    section_type: str | None = None
    section_weight: Decimal

    link_method: str | None = None
    link_confidence: Decimal
    semantic_similarity: Decimal

    intent_label: str
    intent_score: Decimal

    chunk_quality: Decimal
    mention_score: Decimal

    is_internal: bool
    created_at: datetime

    target_document: CanonicalDocumentCitationSummaryResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class CitationMentionListResponse(BaseModel):
    edge: CitationEdgeResponse
    items: list[CitationMentionResponse]


class CitationNetworkNodeResponse(BaseModel):
    canonical_document_id: UUID
    title: str | None = None
    publication_year: int | None = None
    doi: str | None = None
    out_degree: int
    in_degree: int


class CitationNetworkEdgeResponse(BaseModel):
    edge_id: UUID
    source_canonical_id: UUID
    target_canonical_id: UUID
    source_title: str | None = None
    target_title: str | None = None
    citation_score: Decimal
    mention_count: int
    score_band: str | None = None


class CitationNetworkResponse(BaseModel):
    run: CitationScoreRunResponse
    total_nodes: int
    total_edges: int
    nodes: list[CitationNetworkNodeResponse]
    edges: list[CitationNetworkEdgeResponse]
