from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.constants.activity import ActivityEventType
from app.models.activity_log import ActivityLog
from app.models.paper_record import PaperRecord
from app.models.user import User
from app.schemas.admin import (
    AdminEvaluationReportResponse,
    AdminEvaluationSummary,
    ProcessingLogSummaryItem,
    SearchSampleItem,
)


class AdminReportingService:
    def __init__(self, db: Session):
        self.db = db

    def build_evaluation_report(
        self,
        *,
        window_days: int = 7,
        search_sample_limit: int = 20,
    ) -> AdminEvaluationReportResponse:
        if window_days < 1 or window_days > 365:
            window_days = 7
        if search_sample_limit < 1 or search_sample_limit > 100:
            search_sample_limit = 20

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=window_days)

        total_papers = self.db.query(PaperRecord).count()
        published_papers = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.publication_status == "published")
            .count()
        )
        draft_papers = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.publication_status == "draft")
            .count()
        )
        jobs_failed = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.processing_status == "failed")
            .count()
        )
        jobs_processing = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.processing_status.notin_(["completed", "failed"]))
            .count()
        )

        cache_hits = (
            self.db.query(ActivityLog)
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
            self.db.query(ActivityLog)
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
        cache_total = cache_hits + cache_misses
        cache_hit_rate = (cache_hits / cache_total) if cache_total > 0 else 0.0

        avg_pipeline_seconds = (
            self.db.query(
                func.avg(
                    func.extract("epoch", PaperRecord.updated_at - PaperRecord.created_at)
                )
            )
            .filter(PaperRecord.processing_status.in_(["completed", "failed"]))
            .scalar()
        )
        avg_pipeline_seconds_value = (
            float(avg_pipeline_seconds) if avg_pipeline_seconds is not None else None
        )

        processing_error_rows = (
            self.db.query(
                ActivityLog.event_type,
                func.count(ActivityLog.id),
            )
            .filter(ActivityLog.created_at >= start_time)
            .filter(ActivityLog.status == "error")
            .filter(
                or_(
                    ActivityLog.event_type.ilike("parse_%"),
                    ActivityLog.event_type.ilike("semantic_scholar_%"),
                    ActivityLog.event_type.ilike("llm_extraction_%"),
                    ActivityLog.event_type.ilike("duplicate_%"),
                    ActivityLog.event_type.ilike("canonical_%"),
                )
            )
            .group_by(ActivityLog.event_type)
            .order_by(func.count(ActivityLog.id).desc())
            .all()
        )
        processing_errors = [
            ProcessingLogSummaryItem(event_type=event_type, count=count)
            for event_type, count in processing_error_rows
        ]

        search_rows = (
            self.db.query(ActivityLog, User)
            .outerjoin(User, ActivityLog.actor_user_id == User.id)
            .filter(ActivityLog.created_at >= start_time)
            .filter(
                ActivityLog.event_type.in_(
                    [
                        ActivityEventType.SEARCH_SEMANTIC_EXECUTED,
                        ActivityEventType.SEARCH_KEYWORD_EXECUTED,
                    ]
                )
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(search_sample_limit)
            .all()
        )
        search_samples: list[SearchSampleItem] = []
        for activity, user in search_rows:
            metadata = activity.metadata_json or {}
            query_text = str(metadata.get("query") or "").strip()
            if not query_text:
                continue

            top_k_or_limit = int(
                metadata.get("top_k")
                or metadata.get("limit")
                or metadata.get("top_k_or_limit")
                or 0
            )
            result_count = int(metadata.get("result_count") or 0)

            search_samples.append(
                SearchSampleItem(
                    event_type=activity.event_type,
                    created_at=activity.created_at,
                    actor_email=user.email if user else None,
                    query=query_text,
                    result_count=result_count,
                    top_k_or_limit=top_k_or_limit,
                )
            )

        processing_status = self._status_count_map(
            self.db.query(PaperRecord.processing_status, func.count(PaperRecord.id))
            .group_by(PaperRecord.processing_status)
            .all()
        )
        publication_status = self._status_count_map(
            self.db.query(PaperRecord.publication_status, func.count(PaperRecord.id))
            .group_by(PaperRecord.publication_status)
            .all()
        )

        return AdminEvaluationReportResponse(
            generated_at=now,
            window_days=window_days,
            summary=AdminEvaluationSummary(
                total_papers=total_papers,
                draft_papers=draft_papers,
                published_papers=published_papers,
                jobs_processing=jobs_processing,
                jobs_failed=jobs_failed,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                cache_hit_rate=cache_hit_rate,
                avg_pipeline_seconds=avg_pipeline_seconds_value,
            ),
            processing_errors=processing_errors,
            search_samples=search_samples,
            processing_status=processing_status,
            publication_status=publication_status,
            extra_metrics={
                "window_start": start_time.isoformat(),
                "window_end": now.isoformat(),
                "total_activity_logs": self.db.query(ActivityLog).count(),
                "total_processing_logs": self._count_processing_logs(),
            },
        )

    def _count_processing_logs(self) -> int:
        return (
            self.db.query(ActivityLog)
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

    @staticmethod
    def _status_count_map(rows: list[tuple[str | None, int]]) -> dict[str, int]:
        return {(name or "unknown"): count for name, count in rows}
