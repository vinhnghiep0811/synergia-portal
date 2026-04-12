from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    id: UUID
    created_at: datetime

    actor_type: str
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    actor_full_name: str | None = None
    actor_display: str

    event_type: str
    object_type: str
    object_id: UUID

    paper_record_id: UUID | None = None
    canonical_document_id: UUID | None = None

    paper_filename: str | None = None
    canonical_key: str | None = None
    status_label: str
    event_label: str
    status: str
    message: str
    metadata_json: dict[str, Any] | None = None

class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    skip: int
    limit: int
    has_more: bool