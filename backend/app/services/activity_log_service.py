from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.constants.activity import (
    ActivityActorType,
    ActivityEventType,
    ActivityObjectType,
    ActivityStatus,
)


class ActivityLogService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        actor_type: str,
        event_type: str,
        object_type: str,
        object_id: UUID,
        status: str,
        message: str,
        actor_user_id: UUID | None = None,
        paper_record_id: UUID | None = None,
        canonical_document_id: UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ActivityLog:
        activity = ActivityLog(
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            paper_record_id=paper_record_id,
            canonical_document_id=canonical_document_id,
            status=status,
            message=message,
            metadata_json=metadata_json,
        )

        self.db.add(activity)
        return activity

    def log_paper_uploaded(
        self,
        *,
        paper_id: UUID,
        filename: str,
        file_size_bytes: int,
        mime_type: str,
        upload_source: str,
        actor_user_id: UUID | None = None,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.USER,
            actor_user_id=actor_user_id,
            event_type=ActivityEventType.PAPER_UPLOADED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            status=ActivityStatus.SUCCESS,
            message=f'Uploaded paper "{filename}"',
            metadata_json={
                "filename": filename,
                "file_size_bytes": file_size_bytes,
                "mime_type": mime_type,
                "upload_source": upload_source,
            },
        )

    def log_parse_queued(
        self,
        *,
        paper_id: UUID,
        filename: str,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.PARSE_QUEUED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            status=ActivityStatus.INFO,
            message=f'Queued parse job for "{filename}"',
            metadata_json={
                "filename": filename,
                "processing_stage": "queued",
            },
        )

    def log_parse_queue_failed(
        self,
        *,
        paper_id: UUID,
        filename: str,
        error_message: str,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.PARSE_QUEUE_FAILED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            status=ActivityStatus.ERROR,
            message=f'Failed to queue parse job for "{filename}"',
            metadata_json={
                "filename": filename,
                "error_message": error_message,
            },
        )

    def log_parse_started(
        self,
        *,
        paper_id: UUID,
        filename: str,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.PARSE_STARTED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            status=ActivityStatus.INFO,
            message=f'Start parsing "{filename}"',
        )

    def log_parse_completed(
        self,
        *,
        paper_id: UUID,
        canonical_document_id: UUID,
        filename: str,
        doi: str | None,
        title: str | None,
        canonical_key: str,
        canonical_type: str,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.PARSE_COMPLETED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.SUCCESS,
            message=f'Parse completed for "{filename}"',
            metadata_json={
                "doi": doi,
                "title": title,
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
            },
        )

    def log_parse_failed(
        self,
        *,
        paper_id: UUID,
        filename: str,
        error_message: str,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.PARSE_FAILED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            status=ActivityStatus.ERROR,
            message=f'Parse failed for "{filename}"',
            metadata_json={
                "error_message": error_message,
            },
        )

    def log_duplicate_detected(
        self,
        *,
        paper_id: UUID,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
        duplicate_of_paper_id: UUID,
    ) -> ActivityLog:
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.DUPLICATE_DETECTED,
            object_type=ActivityObjectType.PAPER_RECORD,
            object_id=paper_id,
            paper_record_id=paper_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.WARNING,
            message="Duplicate detected and mapped to existing canonical document",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
                "duplicate_of_paper_id": str(duplicate_of_paper_id),
            },
        )
    
    def log_semantic_scholar_started(
        self,
        *,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
        doi: str | None,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.SEMANTIC_SCHOLAR_STARTED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.INFO,
            message="Started Semantic Scholar enrichment",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
                "doi": doi,
            },
        )
    
    def log_semantic_scholar_matched(
        self,
        *,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
        doi: str | None,
        ss_paper_id: str | None,
        title: str | None,
        metadata_source: str | None = None,
    ):
        source = metadata_source or "semantic_scholar"
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.SEMANTIC_SCHOLAR_MATCHED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.SUCCESS,
            message="Metadata matched and enriched canonical document",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
                "doi": doi,
                "ss_paper_id": ss_paper_id,
                "title": title,
                "metadata_source": source,
            },
        )
    
    def log_semantic_scholar_unmatched(
        self,
        *,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
        doi: str | None,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.SEMANTIC_SCHOLAR_UNMATCHED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.WARNING,
            message="Semantic Scholar could not match canonical document",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
                "doi": doi,
            },
        )
    
    def log_semantic_scholar_skipped(
        self,
        *,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
        doi: str | None,
        ss_paper_id: str | None,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.SEMANTIC_SCHOLAR_SKIPPED_CACHE_HIT,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.INFO,
            message="Skipped Semantic Scholar lookup (already enriched)",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
                "doi": doi,
                "ss_paper_id": ss_paper_id,
            },
        )
    
    def log_semantic_scholar_failed(
        self,
        *,
        canonical_document_id: UUID,
        error_message: str,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.SEMANTIC_SCHOLAR_FAILED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.ERROR,
            message="Semantic Scholar enrichment failed",
            metadata_json={
                "error_message": error_message,
            },
        )
    
    def log_llm_extraction_started(
        self,
        *,
        canonical_document_id: UUID,
        canonical_key: str,
        canonical_type: str,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.LLM_EXTRACTION_STARTED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.INFO,
            message="Started LLM extraction",
            metadata_json={
                "canonical_key": canonical_key,
                "canonical_type": canonical_type,
            },
        )
    
    def log_llm_extraction_completed(
        self,
        *,
        canonical_document_id: UUID,
        extraction_run_id: UUID,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.LLM_EXTRACTION_COMPLETED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.SUCCESS,
            message="LLM extraction completed",
            metadata_json={
                "extraction_run_id": str(extraction_run_id),
                "cache_hit": False,
            },
        )
    
    def log_llm_extraction_cache_hit(
        self,
        *,
        canonical_document_id: UUID,
        extraction_run_id: UUID,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.LLM_EXTRACTION_SKIPPED_CACHE_HIT,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.INFO,
            message="Skipped LLM extraction because cached result already exists",
            metadata_json={
                "extraction_run_id": str(extraction_run_id),
                "cache_hit": True,
            },
        )
    
    def log_llm_extraction_failed(
        self,
        *,
        canonical_document_id: UUID,
        error_message: str,
    ):
        return self.log(
            actor_type=ActivityActorType.SYSTEM,
            event_type=ActivityEventType.LLM_EXTRACTION_FAILED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_document_id,
            canonical_document_id=canonical_document_id,
            status=ActivityStatus.ERROR,
            message="LLM extraction failed",
            metadata_json={
                "error_message": error_message,
            },
        )
