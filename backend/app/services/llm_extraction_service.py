import os
import logging
import tempfile
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.schemas.extraction_result import ExtractionResultSchema
from app.services.llm.input_builder import LLMInputBuilder
from app.services.llm.prompt_builder import LLMPromptBuilder
from app.services.llm.constants import PROMPT_VERSION
from app.services.llm.provider_factory import LLMProviderFactory
from app.services.pdf_parse_service import extract_pdf_text_for_llm
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class LLMExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExtractionRunRepository(db)
        self.provider = LLMProviderFactory.create()
        self.input_builder = LLMInputBuilder()
        self.prompt_builder = LLMPromptBuilder()

    def run_for_canonical_document(self, canonical_document_id: UUID) -> ExtractionRun:
        canonical = self._get_canonical_or_raise(canonical_document_id)

        cached_run = self.repo.get_latest_completed_by_canonical_document_id(canonical.id)
        if cached_run:
            logger.info("[LLM SERVICE] Cache hit for canonical_document_id=%s", canonical.id)
            return cached_run

        logger.info("[LLM SERVICE] Cache miss for canonical_document_id=%s", canonical.id)

        run = self._create_running_extraction_run(canonical.id)

        try:
            full_text = self._load_full_text_for_canonical(canonical)
            if not full_text or len(full_text.strip()) < 500:
                logger.warning(
                    "[LLM SERVICE] Skipping LLM due to insufficient text canonical_id=%s",
                    canonical.id,
                )
                raise ValueError("Insufficient text for LLM extraction")

            input_text = self.input_builder.build(
                canonical,
                parsed_text=None,
                full_text=full_text,
            )
            prompt = self.prompt_builder.build_extraction_prompt(input_text)
            provider_result = self.provider.extract_metadata(prompt)

            raw_result = provider_result.get("result_json")
            if raw_result is None:
                raw_text = provider_result.get("raw_text")
                logger.error(
                    "[LLM SERVICE] Invalid JSON from provider. raw_text=%s",
                    raw_text[:2000] if raw_text else None,
                )
                raise ValueError("LLM returned invalid JSON format")

            result_json = self._normalize_result(raw_result)

            run.provider = provider_result.get("provider")
            run.model_name = provider_result.get("model")

            run = self.repo.mark_completed(
                run,
                result_json=result_json,
                problem_statement=result_json.get("problem"),
                main_method=result_json.get("method"),
                contributions=result_json.get("contributions"),
                limitations=result_json.get("limitations"),
                evaluation_setup=result_json.get("evaluation_setup"),
                raw_llm_response=provider_result.get("raw_text"),
                token_input=(provider_result.get("usage") or {}).get("prompt_tokens"),
                token_output=(provider_result.get("usage") or {}).get("completion_tokens"),
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

    def _get_canonical_or_raise(self, canonical_document_id: UUID) -> CanonicalDocument:
        canonical = (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == canonical_document_id)
            .first()
        )
        if not canonical:
            raise ValueError(f"CanonicalDocument not found: {canonical_document_id}")
        return canonical

    def _create_running_extraction_run(self, canonical_document_id: UUID) -> ExtractionRun:
        return self.repo.create(
            ExtractionRun(
                canonical_document_id=canonical_document_id,
                provider="pending",
                model_name="pending",
                prompt_version=PROMPT_VERSION,
                status="running",
                is_from_cache=False,
            )
        )

    def _load_full_text_for_canonical(self, canonical: CanonicalDocument) -> Optional[str]:
        if not canonical.papers:
            return None

        paper = canonical.papers[0]
        if not paper.storage_path:
            return None

        storage = StorageService()
        tmp_path = None

        try:
            pdf_bytes = storage.download_by_storage_path(paper.storage_path)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            full_text, _ = extract_pdf_text_for_llm(tmp_path)
            return full_text

        except Exception as e:
            logger.warning(
                "[LLM SERVICE] Failed to load full text for canonical=%s error=%s",
                canonical.id,
                str(e),
            )
            return None

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _normalize_evidence(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue

            snippet = item.get("snippet")
            if not isinstance(snippet, str) or not snippet.strip():
                continue

            normalized.append(
                {
                    "snippet": snippet.strip(),
                    "page": item.get("page") if isinstance(item.get("page"), int) else None,
                    "section": item.get("section") if isinstance(item.get("section"), str) else None,
                }
            )

        return normalized

    def _normalize_scalar_field(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {"value": None, "evidence": []}

        if isinstance(raw, str):
            return {"value": raw.strip() or None, "evidence": []}

        if not isinstance(raw, dict):
            return {"value": None, "evidence": []}

        value = raw.get("value")
        if not isinstance(value, str):
            value = None
        else:
            value = value.strip() or None

        evidence = self._normalize_evidence(raw.get("evidence"))
        if value and not evidence:
            value = None

        return {
            "value": value,
            "evidence": evidence,
        }

    def _normalize_list_field(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {"items": [], "evidence": []}

        if isinstance(raw, list):
            items = [x.strip() for x in raw if isinstance(x, str) and x.strip()]
            return {"items": items, "evidence": []}

        if not isinstance(raw, dict):
            return {"items": [], "evidence": []}

        raw_items = raw.get("items")
        if raw_items is None:
            raw_items = raw.get("value")

        if not isinstance(raw_items, list):
            raw_items = []

        items = [x.strip() for x in raw_items if isinstance(x, str) and x.strip()]
        evidence = self._normalize_evidence(raw.get("evidence"))

        if items and not evidence:
            items = []

        return {
            "items": items,
            "evidence": evidence,
        }

    def _normalize_evaluation_setup(self, raw: Any) -> dict[str, Any]:
        empty_value = {
            "datasets": [],
            "metrics": [],
            "benchmarks": [],
        }

        if raw is None:
            return {"value": empty_value, "evidence": []}

        if not isinstance(raw, dict):
            return {"value": empty_value, "evidence": []}

        value = raw.get("value")
        if not isinstance(value, dict):
            value = {}

        datasets = [x.strip() for x in value.get("datasets", []) if isinstance(x, str) and x.strip()]
        metrics = [x.strip() for x in value.get("metrics", []) if isinstance(x, str) and x.strip()]
        benchmarks = [x.strip() for x in value.get("benchmarks", []) if isinstance(x, str) and x.strip()]

        evidence = self._normalize_evidence(raw.get("evidence"))

        has_content = bool(datasets or metrics or benchmarks)
        if has_content and not evidence:
            datasets, metrics, benchmarks = [], [], []

        return {
            "value": {
                "datasets": datasets,
                "metrics": metrics,
                "benchmarks": benchmarks,
            },
            "evidence": evidence,
        }

    def _normalize_result(self, raw: dict[str, Any] | None) -> dict[str, Any]:
        raw = raw or {}

        normalized = {
            "problem": self._normalize_scalar_field(raw.get("problem")),
            "method": self._normalize_scalar_field(raw.get("method")),
            "contributions": self._normalize_list_field(raw.get("contributions")),
            "limitations": self._normalize_list_field(raw.get("limitations")),
            "evaluation_setup": self._normalize_evaluation_setup(raw.get("evaluation_setup")),
        }

        return ExtractionResultSchema(**normalized).model_dump()