from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.extraction_run import ExtractionRun
from app.models.canonical_document import CanonicalDocument


class ExtractionRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, extraction_run: ExtractionRun) -> ExtractionRun:
        self.db.add(extraction_run)
        self.db.commit()
        self.db.refresh(extraction_run)
        return extraction_run

    def get_by_id(self, run_id: UUID) -> Optional[ExtractionRun]:
        return (
            self.db.query(ExtractionRun)
            .filter(ExtractionRun.id == run_id)
            .first()
        )

    def get_latest_completed_by_canonical_document_id(
        self,
        canonical_document_id: UUID,
        prompt_version: str | None = None,
    ) -> Optional[ExtractionRun]:
        query = (
            self.db.query(ExtractionRun)
            .filter(
                ExtractionRun.canonical_document_id == canonical_document_id,
                ExtractionRun.status == "completed",
            )
        )

        if prompt_version:
            query = query.filter(ExtractionRun.prompt_version == prompt_version)

        return query.order_by(ExtractionRun.created_at.desc()).first()

    def get_latest_by_canonical_document_id(
        self,
        canonical_document_id: UUID,
    ) -> Optional[ExtractionRun]:
        return (
            self.db.query(ExtractionRun)
            .filter(ExtractionRun.canonical_document_id == canonical_document_id)
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )

    def update(self, extraction_run: ExtractionRun) -> ExtractionRun:
        self.db.add(extraction_run)
        self.db.commit()
        self.db.refresh(extraction_run)
        return extraction_run

    def mark_completed(
        self,
        extraction_run: ExtractionRun,
        *,
        result_json: dict | None,
        problem_statement: dict | None,
        main_method: dict | None,
        contributions: dict | None,
        limitations: dict | None,
        evaluation_setup: dict | None,
        raw_llm_response: dict | None,
        token_input: int | None,
        token_output: int | None,
    ) -> ExtractionRun:
        extraction_run.status = "completed"
        extraction_run.result_json = result_json
        extraction_run.problem_statement = problem_statement
        extraction_run.main_method = main_method
        extraction_run.contributions = contributions
        extraction_run.limitations = limitations
        extraction_run.evaluation_setup = evaluation_setup
        extraction_run.raw_llm_response = raw_llm_response
        extraction_run.token_input = token_input
        extraction_run.token_output = token_output
        extraction_run.error_message = None

        self.db.add(extraction_run)
        self.db.commit()
        self.db.refresh(extraction_run)
        return extraction_run

    def mark_failed(
        self,
        extraction_run: ExtractionRun,
        *,
        error_message: str,
        raw_llm_response: dict | None = None,
    ) -> ExtractionRun:
        extraction_run.status = "failed"
        extraction_run.error_message = error_message
        extraction_run.raw_llm_response = raw_llm_response

        self.db.add(extraction_run)
        self.db.commit()
        self.db.refresh(extraction_run)
        return extraction_run

    def set_latest_for_canonical_document(
        self,
        canonical_document: CanonicalDocument,
        extraction_run: ExtractionRun,
    ) -> CanonicalDocument:
        canonical_document.latest_extraction_run_id = extraction_run.id
        canonical_document.extraction_cache_status = "ready"

        self.db.add(canonical_document)
        self.db.commit()
        self.db.refresh(canonical_document)
        return canonical_document
