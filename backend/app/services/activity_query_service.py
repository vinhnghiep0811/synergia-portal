from uuid import UUID

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
        status: str | None = None,
        paper_record_id: UUID | None = None,
        canonical_document_id: UUID | None = None,
    ) -> dict:
        items, total = self.repo.list_activity_logs(
            skip=skip,
            limit=limit,
            event_type=event_type,
            status=status,
            paper_record_id=paper_record_id,
            canonical_document_id=canonical_document_id,
        )

        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": skip + limit < total,
        }