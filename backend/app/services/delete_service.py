from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants.activity import (
    ActivityActorType,
    ActivityEventType,
    ActivityObjectType,
    ActivityStatus,
)
from app.models.activity_log import ActivityLog
from app.models.canonical_document import CanonicalDocument
from app.models.citation_edge import CitationEdge
from app.models.citation_mention import CitationMention
from app.models.document_chunk import DocumentChunk
from app.models.document_section import DocumentSection
from app.models.extraction_run import ExtractionRun
from app.models.paper_record import PaperRecord
from app.models.publish_version import PublishVersion
from app.services.activity_log_service import ActivityLogService
from app.services.storage_service import StorageService


class DeleteConflictError(ValueError):
    pass


class DeleteService:
    def __init__(self, db: Session):
        self.db = db
        self.activity_service = ActivityLogService(db)
        self.storage = StorageService()

    def delete_paper_record(
        self,
        paper_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> dict:
        paper = self._get_paper_or_none(paper_id)
        if not paper:
            raise LookupError("Paper not found.")

        result = self._delete_paper_record(
            paper,
            actor_user_id=actor_user_id,
            log_event=True,
        )
        self.db.commit()

        storage_result = self._delete_storage_paths(result["storage_paths"])
        result.update(storage_result)
        result.pop("storage_paths", None)
        return result

    def delete_canonical_document(
        self,
        canonical_id: UUID,
        *,
        delete_papers: bool = False,
        actor_user_id: UUID | None = None,
    ) -> dict:
        canonical = self._get_canonical_or_none(canonical_id)
        if not canonical:
            raise LookupError("Canonical document not found.")

        linked_papers = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical_id)
            .all()
        )
        if linked_papers and not delete_papers:
            raise DeleteConflictError(
                "Canonical document still has linked paper records. "
                "Call with delete_papers=true to delete them together."
            )

        storage_paths: list[str] = []
        deleted_publish_versions_count = 0

        for paper in linked_papers:
            paper_result = self._delete_paper_record(
                paper,
                actor_user_id=actor_user_id,
                log_event=True,
            )
            storage_paths.extend(paper_result["storage_paths"])
            deleted_publish_versions_count += paper_result["deleted_publish_versions_count"]

        deleted_citation_mentions_count = (
            self.db.query(CitationMention)
            .filter(CitationMention.source_canonical_id == canonical_id)
            .delete(synchronize_session=False)
        )
        self.db.query(CitationMention).filter(
            CitationMention.target_canonical_id == canonical_id
        ).update(
            {CitationMention.target_canonical_id: None},
            synchronize_session=False,
        )

        deleted_citation_edges_count = (
            self.db.query(CitationEdge)
            .filter(
                or_(
                    CitationEdge.source_canonical_id == canonical_id,
                    CitationEdge.target_canonical_id == canonical_id,
                )
            )
            .delete(synchronize_session=False)
        )

        deleted_document_chunks_count = (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.canonical_document_id == canonical_id)
            .delete(synchronize_session=False)
        )
        deleted_document_sections_count = (
            self.db.query(DocumentSection)
            .filter(DocumentSection.canonical_document_id == canonical_id)
            .delete(synchronize_session=False)
        )

        deleted_extraction_runs_count = self._delete_extraction_runs_for_canonical(
            canonical_id
        )

        self._detach_activity_references(canonical_document_id=canonical_id)

        self.db.query(CanonicalDocument).filter(
            CanonicalDocument.id == canonical_id
        ).delete(synchronize_session=False)

        self.activity_service.log(
            actor_type=ActivityActorType.ADMIN,
            actor_user_id=actor_user_id,
            event_type=ActivityEventType.CANONICAL_DELETED,
            object_type=ActivityObjectType.CANONICAL_DOCUMENT,
            object_id=canonical_id,
            status=ActivityStatus.WARNING,
            message="Deleted canonical document",
            metadata_json={
                "canonical_key": canonical.canonical_key,
                "canonical_type": canonical.canonical_type,
                "doi": canonical.doi,
                "deleted_papers_count": len(linked_papers),
                "deleted_publish_versions_count": deleted_publish_versions_count,
                "deleted_extraction_runs_count": deleted_extraction_runs_count,
                "deleted_document_sections_count": deleted_document_sections_count,
                "deleted_document_chunks_count": deleted_document_chunks_count,
                "deleted_citation_edges_count": deleted_citation_edges_count,
                "deleted_citation_mentions_count": deleted_citation_mentions_count,
            },
        )

        self.db.commit()

        storage_result = self._delete_storage_paths(storage_paths)
        return {
            "id": canonical_id,
            "deleted": True,
            "deleted_papers_count": len(linked_papers),
            "deleted_extraction_runs_count": deleted_extraction_runs_count,
            "deleted_document_sections_count": deleted_document_sections_count,
            "deleted_document_chunks_count": deleted_document_chunks_count,
            "deleted_citation_edges_count": deleted_citation_edges_count,
            "deleted_citation_mentions_count": deleted_citation_mentions_count,
            **storage_result,
        }

    def _delete_paper_record(
        self,
        paper: PaperRecord,
        *,
        actor_user_id: UUID | None,
        log_event: bool,
    ) -> dict:
        paper_id = paper.id
        storage_paths = self._paper_storage_paths(paper)

        deleted_publish_versions_count = (
            self.db.query(PublishVersion)
            .filter(PublishVersion.paper_record_id == paper_id)
            .delete(synchronize_session=False)
        )

        self.db.query(PaperRecord).filter(
            PaperRecord.duplicate_of_paper_id == paper_id
        ).update(
            {
                PaperRecord.duplicate_of_paper_id: None,
                PaperRecord.is_duplicate: False,
            },
            synchronize_session=False,
        )

        self._detach_activity_references(paper_record_id=paper_id)
        self.db.delete(paper)

        if log_event:
            self.activity_service.log(
                actor_type=ActivityActorType.ADMIN,
                actor_user_id=actor_user_id,
                event_type=ActivityEventType.PAPER_DELETED,
                object_type=ActivityObjectType.PAPER_RECORD,
                object_id=paper_id,
                canonical_document_id=paper.canonical_document_id,
                status=ActivityStatus.WARNING,
                message=f'Deleted paper "{paper.original_filename}"',
                metadata_json={
                    "original_filename": paper.original_filename,
                    "storage_paths": storage_paths,
                    "canonical_document_id": (
                        str(paper.canonical_document_id)
                        if paper.canonical_document_id
                        else None
                    ),
                    "deleted_publish_versions_count": deleted_publish_versions_count,
                },
            )

        return {
            "id": paper_id,
            "deleted": True,
            "canonical_document_id": paper.canonical_document_id,
            "deleted_publish_versions_count": deleted_publish_versions_count,
            "storage_paths": storage_paths,
        }

    def _delete_extraction_runs_for_canonical(self, canonical_id: UUID) -> int:
        self.db.query(CanonicalDocument).filter(
            CanonicalDocument.id == canonical_id
        ).update(
            {CanonicalDocument.latest_extraction_run_id: None},
            synchronize_session=False,
        )
        self.db.flush()

        return (
            self.db.query(ExtractionRun)
            .filter(ExtractionRun.canonical_document_id == canonical_id)
            .delete(synchronize_session=False)
        )

    def _detach_activity_references(
        self,
        *,
        paper_record_id: UUID | None = None,
        canonical_document_id: UUID | None = None,
    ) -> None:
        values = {}
        filters = []

        if paper_record_id:
            values[ActivityLog.paper_record_id] = None
            filters.append(ActivityLog.paper_record_id == paper_record_id)

        if canonical_document_id:
            values[ActivityLog.canonical_document_id] = None
            filters.append(ActivityLog.canonical_document_id == canonical_document_id)

        if not filters:
            return

        self.db.query(ActivityLog).filter(or_(*filters)).update(
            values,
            synchronize_session=False,
        )

    def _delete_storage_paths(self, storage_paths: list[str]) -> dict:
        deleted_count = 0
        errors: list[str] = []

        for storage_path in self._unique_storage_paths(storage_paths):
            try:
                if self.storage.delete_by_storage_path(storage_path):
                    deleted_count += 1
            except Exception as exc:
                errors.append(f"{storage_path}: {exc}")

        return {
            "storage_objects_deleted": deleted_count,
            "storage_delete_errors": errors,
        }

    @staticmethod
    def _paper_storage_paths(paper: PaperRecord) -> list[str]:
        return [
            path
            for path in (
                paper.storage_path,
                paper.docling_markdown_storage_path,
                paper.page_text_json_storage_path,
            )
            if path
        ]

    @staticmethod
    def _unique_storage_paths(storage_paths: list[str]) -> list[str]:
        seen = set()
        unique_paths = []
        for storage_path in storage_paths:
            if storage_path in seen:
                continue
            seen.add(storage_path)
            unique_paths.append(storage_path)
        return unique_paths

    def _get_paper_or_none(self, paper_id: UUID) -> PaperRecord | None:
        return (
            self.db.query(PaperRecord)
            .filter(PaperRecord.id == paper_id)
            .first()
        )

    def _get_canonical_or_none(self, canonical_id: UUID) -> CanonicalDocument | None:
        return (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == canonical_id)
            .first()
        )
