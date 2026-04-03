import os
import re
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

    def _detect_paper_type(self, text: str) -> str:
        t = text.lower()

        # ưu tiên system trước
        if any(k in t for k in [
            "we introduce",
            "this paper introduces",
            "this paper presents",
            "we present",
            "metadata format",
            "framework",
            "format",
            "system",
            "architecture",
        ]):
            return "system"

        if any(k in t for k in [
            "survey",
            "review of",
            "we review",
        ]):
            return "survey"

        if any(k in t for k in [
            "experimental results",
            "accuracy",
            "f1 score",
            "outperforms",
            "benchmark",
        ]):
            return "benchmark"

        return "other"
    def _infer_evaluation_evidence_from_pages(
        self,
        pages: list[dict],
    ) -> list[dict[str, Any]]:
        keywords = [
            "evaluation",
            "user study",
            "annotator",
            "annotators",
            "bleu",
            "likert",
            "completeness",
            "readability",
            "understandability",
            "consistency",
        ]

        best_candidate = None

        for page in pages:
            page_num = page.get("page")
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue

            lines = [line.strip() for line in page_text.splitlines() if line.strip()]

            for line in lines:
                lower_line = line.lower()

                if not any(k in lower_line for k in keywords):
                    continue

                # ❌ reject nếu quá nhiều số
                if sum(c.isdigit() for c in line) > len(line) * 0.3:
                    continue

                # ❌ reject nếu bị dính chữ (no spaces)
                if len(line.split()) < 5:
                    continue

                # ưu tiên câu dài hơn (nhiều thông tin hơn)
                if best_candidate is None or len(line) > len(best_candidate["snippet"]):
                    best_candidate = {
                        "snippet": re.sub(r"\s+", " ", line)[:180],
                        "page": page_num if isinstance(page_num, int) else None,
                        "section": None,
                    }

        if best_candidate:
            return [best_candidate]

        return []

    def _apply_semantic_correction(
        self,
        raw_result: dict,
        full_text: str,
    ) -> dict:
        if not raw_result:
            return raw_result

        paper_type = self._detect_paper_type(full_text)

        # 🔥 Fix Croissant-like papers
        if paper_type == "system":
            eval_setup = raw_result.get("evaluation_setup") or {}
            value = eval_setup.get("value") or {}

            # ❌ benchmark không hợp lệ → clear
            value["benchmarks"] = []

            # ✅ infer human metrics
            metrics = []

            t = full_text.lower()

            if "likert" in t:
                metrics.append("Likert scale")

            if "bleu" in t:
                metrics.append("BLEU score")

            if "readability" in t:
                metrics.append("readability")

            if "completeness" in t:
                metrics.append("completeness")

            if "consistency" in t:
                metrics.append("consistency")

            value["metrics"] = metrics

            eval_setup["value"] = value
            raw_result["evaluation_setup"] = eval_setup

        return raw_result

    def run_for_canonical_document(self, canonical_document_id: UUID) -> ExtractionRun:
        canonical = self._get_canonical_or_raise(canonical_document_id)

        cached_run = self.repo.get_latest_completed_by_canonical_document_id(canonical.id)
        if cached_run:
            logger.info("[LLM SERVICE] Cache hit for canonical_document_id=%s", canonical.id)
            return cached_run

        logger.info("[LLM SERVICE] Cache miss for canonical_document_id=%s", canonical.id)

        run = self._create_running_extraction_run(canonical.id)

        try:
            full_text, pages = self._load_full_text_for_canonical(canonical)
            text_len = len((full_text or "").strip())

            logger.info(
                "[LLM SERVICE] canonical_id=%s extracted_text_len=%s",
                canonical.id,
                text_len,
            )

            if text_len < 500:
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
            raw_result = self._apply_semantic_correction(raw_result, full_text)

            result_json = self._normalize_result(raw_result, pages)

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

    def _load_full_text_for_canonical(
    self,
    canonical: CanonicalDocument,
) -> tuple[Optional[str], list[dict]]:
        if not canonical.papers:
            return None, []

        storage = StorageService()

        for paper in canonical.papers:
            if not paper.storage_path:
                continue

            tmp_path = None

            try:
                pdf_bytes = storage.download_by_storage_path(paper.storage_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(pdf_bytes)
                    tmp_path = tmp.name

                full_text, _, pages = extract_pdf_text_for_llm(tmp_path)
                text_len = len((full_text or "").strip())

                logger.info(
                    "[LLM SERVICE] Loaded text for canonical=%s paper_id=%s text_len=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    text_len,
                )

                if text_len > 0:
                    return full_text, pages

            except Exception as e:
                logger.warning(
                    "[LLM SERVICE] Failed to load full text for canonical=%s paper_id=%s error=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    str(e),
                )

            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        return None, []

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

            snippet = snippet.strip()

            # loại table numeric
            if sum(c.isdigit() for c in snippet) > len(snippet) * 0.4:
                continue

            # loại multi-line numeric dump
            if "\n" in snippet and any(c.isdigit() for c in snippet):
                continue

            # repair spacing mạnh hơn
            snippet = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', snippet)
            snippet = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', snippet)
            snippet = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', snippet)
            snippet = re.sub(r'(?<=[,.;:])(?=[A-Za-z])', ' ', snippet)

            # xử lý một số pattern dính phổ biến
            snippet = re.sub(r'(?<=[a-z])(?=[A-Z][a-z])', ' ', snippet)
            # fix missing spaces heuristic
            # snippet = re.sub(r'([a-z])([a-z]{2,})', r'\1 \2', snippet)
            snippet = re.sub(r'\s+', ' ', snippet).strip()

            if not snippet:
                continue

            if len(snippet) > 180:
                cut = snippet[:180]
                last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
                if last_stop > 80:
                    snippet = cut[:last_stop].strip()
                else:
                    snippet = cut.strip()

            normalized.append(
                {
                    "snippet": snippet,
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
            # case 1: ["a", "b"]
            if all(isinstance(x, str) for x in raw):
                items = [x.strip() for x in raw if isinstance(x, str) and x.strip()]
                return {"items": items, "evidence": []}

            # case 2: [{"value": "...", "evidence": [...]}, ...]
            items: list[str] = []
            merged_evidence: list[dict[str, Any]] = []

            for x in raw:
                if not isinstance(x, dict):
                    continue

                value = x.get("value")
                if isinstance(value, str) and value.strip():
                    items.append(value.strip())

                merged_evidence.extend(self._normalize_evidence(x.get("evidence")))

            if items and not merged_evidence:
                items = []

            return {
                "items": items,
                "evidence": merged_evidence,
            }

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

    def _normalize_evaluation_setup(
        self,
        raw: Any,
        pages: list[dict],
    ) -> dict[str, Any]:
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

        # 🔥 fallback nếu evidence bị drop
        if has_content and not evidence:
            fallback = self._infer_evaluation_evidence_from_pages(pages)
            if fallback:
                logger.info("[LLM NORMALIZE] Using fallback evidence for evaluation_setup")
                evidence = fallback

        # ❗ nếu vẫn không có evidence → drop để pass schema
        if has_content and not evidence:
            logger.warning("[LLM NORMALIZE] Dropping evaluation_setup due to missing evidence")
            return {"value": empty_value, "evidence": []}

        return {
            "value": {
                "datasets": datasets,
                "metrics": metrics,
                "benchmarks": benchmarks,
            },
            "evidence": evidence,
        }

    def _normalize_result(self, raw: dict[str, Any] | None, pages: list[dict]) -> dict[str, Any]:
        raw = raw or {}

        normalized = {
            "problem": self._normalize_scalar_field(raw.get("problem")),
            "method": self._normalize_scalar_field(raw.get("method")),
            "contributions": self._normalize_list_field(raw.get("contributions")),
            "limitations": self._normalize_list_field(raw.get("limitations")),
            "evaluation_setup": self._normalize_evaluation_setup(raw.get("evaluation_setup"), pages),
        }
        normalized["problem"] = self._fill_missing_pages(normalized["problem"], pages)
        normalized["method"] = self._fill_missing_pages(normalized["method"], pages)
        normalized["contributions"] = self._fill_missing_pages(normalized["contributions"], pages)
        normalized["limitations"] = self._fill_missing_pages(normalized["limitations"], pages)
        normalized["evaluation_setup"] = self._fill_missing_pages(normalized["evaluation_setup"], pages)
        return ExtractionResultSchema(**normalized).model_dump()
    
    def _match_snippet_to_page(
        self,
        snippet: str,
        pages: list[dict],
    ) -> int | None:
        snippet = (snippet or "").strip()
        if not snippet:
            return None

        for page in pages:
            page_num = page.get("page")
            page_text = (page.get("text") or "").strip()

            if page_text and snippet in page_text:
                return page_num

        return None
    
    def _fill_missing_pages(
        self,
        field_obj: dict[str, Any],
        pages: list[dict],
    ) -> dict[str, Any]:
        evidences = field_obj.get("evidence") or []

        for ev in evidences:
            if ev.get("page") is None:
                matched_page = self._match_snippet_to_page(
                    ev.get("snippet", ""),
                    pages,
                )
                if matched_page is not None:
                    ev["page"] = matched_page

        return field_obj