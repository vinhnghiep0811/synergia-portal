from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db
from app.core.security import require_admin
from app.constants.activity import ActivityEventType
from app.models.activity_log import ActivityLog
from app.models.paper_record import PaperRecord
from app.models.user import User

router = APIRouter()


@router.get("/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    total_papers = db.query(PaperRecord).count()

    processing_rows = (
        db.query(PaperRecord.processing_status, func.count(PaperRecord.id))
        .group_by(PaperRecord.processing_status)
        .all()
    )

    publication_rows = (
        db.query(PaperRecord.publication_status, func.count(PaperRecord.id))
        .group_by(PaperRecord.publication_status)
        .all()
    )

    stage_rows = (
        db.query(PaperRecord.processing_stage, func.count(PaperRecord.id))
        .group_by(PaperRecord.processing_stage)
        .all()
    )

    duplicate_count = (
        db.query(PaperRecord)
        .filter(PaperRecord.is_duplicate.is_(True))
        .count()
    )

    jobs_processing = (
        db.query(PaperRecord)
        .filter(PaperRecord.processing_status.notin_(["completed", "failed"]))
        .count()
    )
    jobs_failed = (
        db.query(PaperRecord)
        .filter(PaperRecord.processing_status == "failed")
        .count()
    )
    cache_hits = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.event_type.in_(
                [
                    ActivityEventType.LLM_EXTRACTION_SKIPPED_CACHE_HIT,
                    ActivityEventType.SEMANTIC_SCHOLAR_SKIPPED_CACHE_HIT,
                ]
            )
        )
        .count()
    )
    cache_misses = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.event_type.in_(
                [
                    ActivityEventType.LLM_EXTRACTION_STARTED,
                    ActivityEventType.SEMANTIC_SCHOLAR_STARTED,
                ]
            )
        )
        .count()
    )
    total_activity_logs = db.query(ActivityLog).count()
    total_processing_logs = (
        db.query(ActivityLog)
        .filter(
            or_(
                ActivityLog.event_type.ilike("parse_%"),
                ActivityLog.event_type.ilike("semantic_scholar_%"),
                ActivityLog.event_type.ilike("llm_extraction_%"),
                ActivityLog.event_type.ilike("duplicate_%"),
                ActivityLog.event_type.ilike("canonical_%"),
            )
        )
        .count()
    )

    return {
        "total_papers": total_papers,
        "processing_status": {
            (status if status is not None else "unknown"): count
            for status, count in processing_rows
        },
        "processing_stage": {
            (stage if stage is not None else "unknown"): count
            for stage, count in stage_rows
        },
        "publication_status": {
            (status if status is not None else "unknown"): count
            for status, count in publication_rows
        },
        "duplicate_count": duplicate_count,
        "operations": {
            "jobs_processing": jobs_processing,
            "jobs_failed": jobs_failed,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "total_activity_logs": total_activity_logs,
            "total_processing_logs": total_processing_logs,
        },
        "current_admin": {
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
        },
    }
