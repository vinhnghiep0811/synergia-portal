from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from app.schemas.canonical_document import CanonicalDocumentEmbeddedResponse

class PaperUploadResponse(BaseModel):
    id: UUID
    original_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    file_hash_sha256: str

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str

    upload_source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperListItemResponse(BaseModel):
    id: UUID
    original_filename: str

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str

    mime_type: str
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperDetailResponse(BaseModel):
    id: UUID
    canonical_document_id: Optional[UUID] = None
    uploader_id: Optional[str] = None

    original_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    file_hash_sha256: str

    upload_source: str

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str
    processing_error: Optional[str] = None

    extracted_text_preview: Optional[str] = None
    detected_doi: Optional[str] = None
    detected_fingerprint: Optional[str] = None
    detected_title: Optional[str] = None

    is_duplicate: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperInCanonicalResponse(BaseModel):
    id: UUID
    canonical_document_id: Optional[UUID] = None
    original_filename: str

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str

    detected_title: Optional[str] = None
    detected_doi: Optional[str] = None
    is_duplicate: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AdminPaperCanonicalSummaryResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    doi: Optional[str] = None
    publication_year: Optional[int] = None
    venue: Optional[str] = None
    enrichment_status: str
    match_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminPaperListItemResponse(BaseModel):
    id: UUID
    canonical_document_id: Optional[UUID] = None
    duplicate_of_paper_id: Optional[UUID] = None
    uploader_id: Optional[str] = None

    original_filename: str
    detected_title: Optional[str] = None

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str

    is_duplicate: bool

    created_at: datetime
    updated_at: datetime

    canonical_document: Optional[AdminPaperCanonicalSummaryResponse] = None

    model_config = ConfigDict(from_attributes=True)

class AdminPaperDetailResponse(BaseModel):
    id: UUID
    canonical_document_id: Optional[UUID] = None
    duplicate_of_paper_id: Optional[UUID] = None
    uploader_id: Optional[str] = None

    original_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    file_hash_sha256: str

    upload_source: str

    processing_status: str
    processing_stage: Optional[str] = None
    publication_status: str
    processing_error: Optional[str] = None

    extracted_text_preview: Optional[str] = None
    detected_doi: Optional[str] = None
    detected_fingerprint: Optional[str] = None
    detected_title: Optional[str] = None

    is_duplicate: bool

    created_at: datetime
    updated_at: datetime

    canonical_document: Optional["CanonicalDocumentEmbeddedResponse"] = None

    model_config = ConfigDict(from_attributes=True)

class PaginationMetaResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class AdminPaperListPaginatedResponse(BaseModel):
    items: list[AdminPaperListItemResponse]
    pagination: PaginationMetaResponse


class PaperDeleteResponse(BaseModel):
    id: UUID
    deleted: bool
    canonical_document_id: Optional[UUID] = None
    deleted_publish_versions_count: int
    storage_objects_deleted: int
    storage_delete_errors: list[str]
