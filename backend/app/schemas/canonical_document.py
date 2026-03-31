from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CanonicalDocumentResponse(BaseModel):
    id: UUID

    canonical_key: str
    canonical_type: str

    doi: Optional[str] = None
    fingerprint: Optional[str] = None

    # Du lieu thu truoc khi enrich
    title_candidate: Optional[str] = None

    # Du lieu sau khi enrich tu Semantic Scholar
    title: Optional[str] = None
    abstract: Optional[str] = None
    venue: Optional[str] = None
    publication_year: Optional[int] = None
    authors_json: Optional[Any] = None

    # Semantic Scholar match info
    ss_paper_id: Optional[str] = None
    ss_match_confidence: Optional[Decimal] = None
    metadata_source: Optional[str] = None
    enrichment_status: str
    match_status: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CanonicalDocumentListItemResponse(BaseModel):
    """Phan hoi ngan gon cho danh sach, khong tra abstract."""
    id: UUID
    canonical_key: str
    canonical_type: str
    doi: Optional[str] = None
    title: Optional[str] = None
    title_candidate: Optional[str] = None
    publication_year: Optional[int] = None
    venue: Optional[str] = None
    enrichment_status: str
    match_status: Optional[str] = None
    metadata_source: Optional[str] = None
    created_at: datetime
    paper_count: int

    model_config = ConfigDict(from_attributes=True)