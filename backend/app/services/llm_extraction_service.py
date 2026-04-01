import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.repositories.extraction_run_repository import ExtractionRunRepository


logger = logging.getLogger(__name__)


class LLMExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExtractionRunRepository(db)

    def run_for_canonical_document(self, canonical_document_id: UUID) -> ExtractionRun:
        canonical = (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == canonical_document_id)
            .first()
        )

        if not canonical:
            raise ValueError(f"CanonicalDocument not found: {canonical_document_id}")

        # 1. cache check
        cached_run = self.repo.get_latest_completed_by_canonical_document_id(canonical.id)
        if cached_run:
            logger.info("[LLM SERVICE] Cache hit for canonical_document_id=%s", canonical.id)
            return cached_run

        logger.info("[LLM SERVICE] Cache miss for canonical_document_id=%s", canonical.id)

        # 2. create run
        run = self.repo.create(
            ExtractionRun(
                canonical_document_id=canonical.id,
                provider="ollama",      # hard-code tạm, config sau
                model_name="llama3",    # hard-code tạm, config sau
                prompt_version="v1",
                status="running",
                is_from_cache=False,
            )
        )

        try:
            # 3. prepare input
            input_text = self._build_input_text(canonical)

            # 4. call LLM (mock trước)
            llm_response = self._mock_extract(input_text)

            # 5. validate / normalize output
            result_json = self._normalize_result(llm_response)

            # 6. save completed run
            run = self.repo.mark_completed(
                run,
                result_json=result_json,
                problem_statement=result_json.get("problem_statement"),
                main_method=result_json.get("main_method"),
                contributions=result_json.get("contributions"),
                limitations=result_json.get("limitations"),
                evaluation_setup=result_json.get("evaluation_setup"),
                raw_llm_response=llm_response,
                token_input=None,
                token_output=None,
            )

            self.repo.set_latest_for_canonical_document(canonical, run)
            return run

        except Exception as e:
            self.repo.mark_failed(
                run,
                error_message=str(e),
                raw_llm_response=None,
            )

            canonical.extraction_cache_status = "failed"
            self.db.add(canonical)
            self.db.commit()
            raise

    def _build_input_text(self, canonical: CanonicalDocument) -> str:
        parts: list[str] = []

        if canonical.title:
            parts.append(f"Title: {canonical.title}")

        if canonical.abstract:
            parts.append(f"Abstract:\n{canonical.abstract}")

        if canonical.title_candidate and canonical.title_candidate != canonical.title:
            parts.append(f"Detected title candidate: {canonical.title_candidate}")

        return "\n\n".join(parts).strip()

    def _mock_extract(self, input_text: str) -> dict[str, Any]:
        logger.info("[LLM SERVICE] Mock extracting, input_length=%s", len(input_text))

        return {
            "problem_statement": None,
            "main_method": None,
            "contributions": None,
            "limitations": None,
            "evaluation_setup": None,
        }

    def _normalize_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "problem_statement": raw.get("problem_statement"),
            "main_method": raw.get("main_method"),
            "contributions": raw.get("contributions"),
            "limitations": raw.get("limitations"),
            "evaluation_setup": raw.get("evaluation_setup"),
        }