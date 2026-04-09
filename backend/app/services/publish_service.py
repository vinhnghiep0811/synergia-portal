from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.models.paper_record import PaperRecord
from app.models.publish_version import PublishVersion
from app.schemas.publish import (
    PublishEvaluationSetup,
    PublishMetadataPayload,
    PublishMetadataPreviewResponse,
    PublishMetadataUpdateRequest,
    PublishVersionCreateResponse,
)


class PublishService:
    def __init__(self, db: Session):
        self.db = db

    def get_publish_preview(self, paper_id: UUID) -> PublishMetadataPreviewResponse:
        paper = self._get_paper_or_raise(paper_id)
        canonical = self._get_canonical_for_paper(paper)
        extraction = self._get_latest_extraction_for_paper(paper)

        base_metadata = self._build_base_metadata(
            paper=paper,
            canonical=canonical,
            extraction=extraction,
        )
        is_editing_draft = self._has_draft_metadata(paper)
        merged_metadata = self._apply_draft_overrides(base_metadata, paper)

        return PublishMetadataPreviewResponse(
            paper_id=paper.id,
            canonical_document_id=paper.canonical_document_id,
            source_extraction_id=extraction.id if extraction else None,
            publication_status=paper.publication_status,
            is_editing_draft=is_editing_draft,
            semantic_status=(canonical.enrichment_status if canonical else None),
            extraction_status=(extraction.status if extraction else None),
            metadata=merged_metadata,
            updated_at=paper.updated_at,
        )

    def update_publish_draft(
        self,
        paper_id: UUID,
        payload: PublishMetadataUpdateRequest,
    ) -> PublishMetadataPreviewResponse:
        paper = self._get_paper_or_raise(paper_id)

        paper.publish_title_draft = self._clean_text(payload.title)
        paper.publish_abstract_draft = self._clean_text(payload.abstract)
        paper.publish_venue_draft = self._clean_text(payload.venue)
        paper.publish_year_draft = payload.year

        paper.publish_authors_draft = self._clean_str_list(payload.authors)
        paper.publish_problem_statement_draft = self._clean_text(payload.problem_statement)
        paper.publish_main_method_draft = self._clean_text(payload.main_method)
        paper.publish_contributions_draft = self._clean_str_list(payload.contributions)
        paper.publish_limitations_draft = self._clean_str_list(payload.limitations)
        paper.publish_evaluation_setup_draft = {
            "datasets": self._clean_str_list(payload.evaluation_setup.datasets),
            "metrics": self._clean_str_list(payload.evaluation_setup.metrics),
            "benchmarks": self._clean_str_list(payload.evaluation_setup.benchmarks),
        }

        self.db.add(paper)
        self.db.commit()
        self.db.refresh(paper)

        return self.get_publish_preview(paper.id)

    def publish(self, paper_id: UUID, published_by: str | None) -> PublishVersionCreateResponse:
        paper = self._get_paper_or_raise(paper_id)

        if not paper.canonical_document_id:
            raise ValueError("Paper has not been linked to a canonical document yet.")

        preview = self.get_publish_preview(paper.id)
        if preview.source_extraction_id is None:
            raise ValueError("No extraction result available for publishing.")

        metadata = preview.metadata

        latest_version = (
            self.db.query(PublishVersion)
            .filter(PublishVersion.paper_record_id == paper.id)
            .order_by(PublishVersion.version_number.desc(), PublishVersion.created_at.desc())
            .first()
        )
        next_version_number = (latest_version.version_number + 1) if latest_version else 1

        evaluation_setup_value = metadata.evaluation_setup.model_dump()
        has_evaluation_setup = any(evaluation_setup_value.values())

        published_at = datetime.now(timezone.utc)

        publish_version = PublishVersion(
            paper_record_id=paper.id,
            source_extraction_id=preview.source_extraction_id,
            version_number=next_version_number,
            status="published",
            title_override=metadata.title,
            abstract_override=metadata.abstract,
            venue_override=metadata.venue,
            year_override=metadata.year,
            authors_override=metadata.authors,
            problem_statement_final=self._to_scalar_with_empty_evidence(metadata.problem_statement),
            main_method_final=self._to_scalar_with_empty_evidence(metadata.main_method),
            contributions_final=self._to_list_with_empty_evidence(metadata.contributions),
            limitations_final=self._to_list_with_empty_evidence(metadata.limitations),
            evaluation_setup_final=(
                {"value": evaluation_setup_value, "evidence": []}
                if has_evaluation_setup
                else None
            ),
            published_by=published_by,
            published_at=published_at,
        )

        paper.publication_status = "published"

        self.db.add(publish_version)
        self.db.add(paper)
        self.db.commit()
        self.db.refresh(publish_version)
        self.db.refresh(paper)

        return PublishVersionCreateResponse(
            paper_id=paper.id,
            publish_version_id=publish_version.id,
            version_number=publish_version.version_number,
            publication_status=paper.publication_status,
            published_at=publish_version.published_at or published_at,
        )

    def _get_paper_or_raise(self, paper_id: UUID) -> PaperRecord:
        paper = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.id == paper_id)
            .first()
        )
        if not paper:
            raise ValueError("Paper not found.")
        return paper

    def _get_canonical_for_paper(self, paper: PaperRecord) -> CanonicalDocument | None:
        if not paper.canonical_document_id:
            return None

        return (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == paper.canonical_document_id)
            .first()
        )

    def _get_latest_extraction_for_paper(self, paper: PaperRecord) -> ExtractionRun | None:
        if not paper.canonical_document_id:
            return None

        return (
            self.db.query(ExtractionRun)
            .filter(ExtractionRun.canonical_document_id == paper.canonical_document_id)
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )

    def _build_base_metadata(
        self,
        *,
        paper: PaperRecord,
        canonical: CanonicalDocument | None,
        extraction: ExtractionRun | None,
    ) -> PublishMetadataPayload:
        title = None
        abstract = None
        venue = None
        year = None
        authors: list[str] = []

        if canonical:
            title = canonical.title or canonical.title_candidate
            abstract = canonical.abstract
            venue = canonical.venue
            year = canonical.publication_year
            authors = self._extract_author_names(canonical.authors_json)

        if not title:
            title = paper.detected_title or paper.original_filename

        problem_statement = self._extract_scalar_value(extraction.problem_statement if extraction else None)
        main_method = self._extract_scalar_value(extraction.main_method if extraction else None)
        contributions = self._extract_list_values(extraction.contributions if extraction else None)
        limitations = self._extract_list_values(extraction.limitations if extraction else None)
        evaluation_setup = self._extract_evaluation_setup(extraction.evaluation_setup if extraction else None)

        return PublishMetadataPayload(
            title=self._clean_text(title),
            abstract=self._clean_text(abstract),
            venue=self._clean_text(venue),
            year=year,
            authors=authors,
            problem_statement=self._clean_text(problem_statement),
            main_method=self._clean_text(main_method),
            contributions=contributions,
            limitations=limitations,
            evaluation_setup=evaluation_setup,
        )

    def _has_draft_metadata(self, paper: PaperRecord) -> bool:
        return any(
            value is not None
            for value in [
                paper.publish_title_draft,
                paper.publish_abstract_draft,
                paper.publish_venue_draft,
                paper.publish_year_draft,
                paper.publish_authors_draft,
                paper.publish_problem_statement_draft,
                paper.publish_main_method_draft,
                paper.publish_contributions_draft,
                paper.publish_limitations_draft,
                paper.publish_evaluation_setup_draft,
            ]
        )

    def _apply_draft_overrides(
        self,
        base_metadata: PublishMetadataPayload,
        paper: PaperRecord,
    ) -> PublishMetadataPayload:
        metadata = base_metadata.model_dump()

        if paper.publish_title_draft is not None:
            metadata["title"] = self._clean_text(paper.publish_title_draft)
        if paper.publish_abstract_draft is not None:
            metadata["abstract"] = self._clean_text(paper.publish_abstract_draft)
        if paper.publish_venue_draft is not None:
            metadata["venue"] = self._clean_text(paper.publish_venue_draft)
        if paper.publish_year_draft is not None:
            metadata["year"] = paper.publish_year_draft

        if paper.publish_authors_draft is not None:
            metadata["authors"] = self._clean_str_list(paper.publish_authors_draft)

        if paper.publish_problem_statement_draft is not None:
            metadata["problem_statement"] = self._clean_text(paper.publish_problem_statement_draft)
        if paper.publish_main_method_draft is not None:
            metadata["main_method"] = self._clean_text(paper.publish_main_method_draft)

        if paper.publish_contributions_draft is not None:
            metadata["contributions"] = self._clean_str_list(paper.publish_contributions_draft)
        if paper.publish_limitations_draft is not None:
            metadata["limitations"] = self._clean_str_list(paper.publish_limitations_draft)

        if paper.publish_evaluation_setup_draft is not None:
            metadata["evaluation_setup"] = {
                "datasets": self._clean_str_list(
                    (paper.publish_evaluation_setup_draft or {}).get("datasets")
                ),
                "metrics": self._clean_str_list(
                    (paper.publish_evaluation_setup_draft or {}).get("metrics")
                ),
                "benchmarks": self._clean_str_list(
                    (paper.publish_evaluation_setup_draft or {}).get("benchmarks")
                ),
            }

        return PublishMetadataPayload(**metadata)

    def _extract_author_names(self, authors_json: Any) -> list[str]:
        if not isinstance(authors_json, list):
            return []

        names: list[str] = []
        for item in authors_json:
            if isinstance(item, dict):
                name = self._clean_text(item.get("name"))
            else:
                name = self._clean_text(item)
            if name:
                names.append(name)

        return names

    def _extract_scalar_value(self, field: Any) -> str | None:
        if field is None:
            return None

        if isinstance(field, dict):
            return self._clean_text(field.get("value"))

        return self._clean_text(field)

    def _extract_list_values(self, field: Any) -> list[str]:
        if not isinstance(field, list):
            return []

        values: list[str] = []
        for item in field:
            if isinstance(item, dict):
                value = self._clean_text(item.get("value"))
            else:
                value = self._clean_text(item)
            if value:
                values.append(value)

        return values

    def _extract_evaluation_setup(self, field: Any) -> PublishEvaluationSetup:
        if not isinstance(field, dict):
            return PublishEvaluationSetup()

        value = field.get("value")
        if not isinstance(value, dict):
            return PublishEvaluationSetup()

        return PublishEvaluationSetup(
            datasets=self._clean_str_list(value.get("datasets")),
            metrics=self._clean_str_list(value.get("metrics")),
            benchmarks=self._clean_str_list(value.get("benchmarks")),
        )

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None

        text = str(value).strip()
        return text if text else None

    def _clean_str_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []

        cleaned: list[str] = []
        for value in values:
            text = self._clean_text(value)
            if text:
                cleaned.append(text)
        return cleaned

    def _to_scalar_with_empty_evidence(self, value: str | None) -> dict[str, Any] | None:
        text = self._clean_text(value)
        if text is None:
            return None
        return {"value": text, "evidence": []}

    def _to_list_with_empty_evidence(self, values: list[str]) -> list[dict[str, Any]]:
        return [{"value": value, "evidence": []} for value in self._clean_str_list(values)]
