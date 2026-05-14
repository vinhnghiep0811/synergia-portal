from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.activity_log_repository import ActivityLogRepository


class ActivityQueryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ActivityLogRepository(db)

    def list_activity_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        event_type: str | None = None,
        event_types: list[str] | None = None,
        event_prefix: str | None = None,
        status: str | None = None,
        actor_type: str | None = None,
        paper_record_id: UUID | None = None,
        canonical_document_id: UUID | None = None,
        created_from: datetime | None = None,
    ) -> dict:
        items, total = self.repo.list_activity_logs(
            skip=skip,
            limit=limit,
            event_type=event_type,
            event_types=event_types,
            event_prefix=event_prefix,
            status=status,
            actor_type=actor_type,
            paper_record_id=paper_record_id,
            canonical_document_id=canonical_document_id,
            created_from=created_from,
        )

        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": skip + limit < total,
        }
