from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PublishEvaluationSetup(BaseModel):
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    benchmarks: list[str] = Field(default_factory=list)


class PublishMetadataPayload(BaseModel):
    title: str | None = None
    abstract: str | None = None
    venue: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)

    problem_statement: str | None = None
    main_method: str | None = None
    contributions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evaluation_setup: PublishEvaluationSetup = Field(default_factory=PublishEvaluationSetup)


class PublishMetadataPreviewResponse(BaseModel):
    paper_id: UUID
    canonical_document_id: UUID | None = None
    source_extraction_id: UUID | None = None

    publication_status: str
    is_editing_draft: bool

    semantic_status: str | None = None
    extraction_status: str | None = None

    metadata: PublishMetadataPayload
    updated_at: datetime


class PublishMetadataUpdateRequest(PublishMetadataPayload):
    pass


class PublishVersionCreateResponse(BaseModel):
    paper_id: UUID
    publish_version_id: UUID
    version_number: int
    publication_status: str
    published_at: datetime
