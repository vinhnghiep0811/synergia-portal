from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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