from uuid import UUID

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.models.paper_record import PaperRecord
from app.models.canonical_document import CanonicalDocument


class ActivityLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_activity_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        event_type: str | None = None,
        status: str | None = None,
        paper_record_id: UUID | None = None,
        canonical_document_id: UUID | None = None,
    ) -> tuple[list[dict], int]:
        base_query = self.db.query(ActivityLog)

        # filter cho base_query (để count đúng)
        if event_type:
            base_query = base_query.filter(ActivityLog.event_type == event_type)

        if status:
            base_query = base_query.filter(ActivityLog.status == status)

        if paper_record_id:
            base_query = base_query.filter(ActivityLog.paper_record_id == paper_record_id)

        if canonical_document_id:
            base_query = base_query.filter(
                ActivityLog.canonical_document_id == canonical_document_id
            )

        # 👉 total count (KHÔNG join)
        total = base_query.count()

        # 👉 query chính có join để lấy data hiển thị
        query = (
            self.db.query(ActivityLog, User, PaperRecord, CanonicalDocument)
            .outerjoin(User, ActivityLog.actor_user_id == User.id)
            .outerjoin(PaperRecord, ActivityLog.paper_record_id == PaperRecord.id)
            .outerjoin(
                CanonicalDocument,
                ActivityLog.canonical_document_id == CanonicalDocument.id,
            )
        )

        # apply lại filter cho query chính
        if event_type:
            query = query.filter(ActivityLog.event_type == event_type)

        if status:
            query = query.filter(ActivityLog.status == status)

        if paper_record_id:
            query = query.filter(ActivityLog.paper_record_id == paper_record_id)

        if canonical_document_id:
            query = query.filter(
                ActivityLog.canonical_document_id == canonical_document_id
            )

        rows = (
            query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results: list[dict] = []
        for activity, user, paper, canonical in rows:
            actor_display = "System"
            if activity.actor_type == "user":
                if user and user.full_name:
                    actor_display = user.full_name
                elif user and user.email:
                    actor_display = user.email
                else:
                    actor_display = "Unknown user"

            paper_filename = None
            if paper and paper.original_filename:
                paper_filename = paper.original_filename
            elif activity.metadata_json and activity.metadata_json.get("filename"):
                paper_filename = activity.metadata_json.get("filename")

            canonical_key = None
            if canonical and canonical.canonical_key:
                canonical_key = canonical.canonical_key
            elif activity.metadata_json and activity.metadata_json.get("canonical_key"):
                canonical_key = activity.metadata_json.get("canonical_key")

            status_label = self._build_status_label(activity.status)

            results.append(
                {
                    "id": activity.id,
                    "created_at": activity.created_at,
                    "actor_type": activity.actor_type,
                    "actor_user_id": activity.actor_user_id,
                    "actor_email": user.email if user else None,
                    "actor_full_name": user.full_name if user else None,
                    "actor_display": actor_display,
                    "event_type": activity.event_type,
                    "event_label": self._build_event_label(activity.event_type),
                    "object_type": activity.object_type,
                    "object_id": activity.object_id,
                    "paper_record_id": activity.paper_record_id,
                    "canonical_document_id": activity.canonical_document_id,
                    "paper_filename": paper_filename,
                    "canonical_key": canonical_key,
                    "status_label": status_label,
                    "status": activity.status,
                    "message": activity.message,
                    "metadata_json": activity.metadata_json,
                }
            )

        return results, total

    @staticmethod
    def _build_event_label(event_type: str) -> str:
        mapping = {
            "paper_uploaded": "Paper uploaded",
            "parse_queued": "Parse queued",
            "parse_queue_failed": "Parse queue failed",
            "parse_started": "Parse started",
            "parse_completed": "Parse completed",
            "parse_failed": "Parse failed",
            "duplicate_detected": "Duplicate detected",
            "semantic_scholar_started": "Semantic Scholar started",
            "semantic_scholar_matched": "Semantic Scholar matched",
            "semantic_scholar_unmatched": "Semantic Scholar unmatched",
            "semantic_scholar_failed": "Semantic Scholar failed",
            "llm_extraction_started": "LLM extraction started",
            "llm_extraction_completed": "LLM extraction completed",
            "llm_extraction_failed": "LLM extraction failed",
            "llm_extraction_skipped_cache_hit": "LLM skipped (cache hit)",
            "paper_published": "Paper published",
        }
        return mapping.get(event_type, event_type.replace("_", " ").title())

    @staticmethod
    def _build_status_label(status: str) -> str:
        mapping = {
            "info": "Info",
            "success": "Success",
            "warning": "Warning",
            "error": "Error",
        }
        return mapping.get(status, status.capitalize())