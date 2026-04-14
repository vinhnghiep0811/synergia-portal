import os
import re
import logging
import json
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

    def _has_expected_extraction_schema(self, raw_result: Any) -> bool:
        if not isinstance(raw_result, dict):
            return False

        required_keys = {
            "problem",
            "method",
            "contributions",
            "limitations",
            "evaluation_setup",
        }

        return required_keys.issubset(set(raw_result.keys()))

    def _schema_keys_for_log(self, raw_result: Any) -> str:
        if isinstance(raw_result, dict):
            return ",".join(sorted(raw_result.keys()))
        return type(raw_result).__name__

    def _normalize_free_text(self, value: Any, max_chars: int = 220) -> str | None:
        if not isinstance(value, str):
            return None

        text = re.sub(r"\s+", " ", value).strip()
        if not text:
            return None

        if self._is_placeholder_text(text):
            return None

        if len(text) > max_chars:
            cut = text[:max_chars]
            last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
            if last_stop > 80:
                text = cut[:last_stop].strip()
            else:
                text = cut.strip()

        return text or None

    def _to_string_list(self, value: Any, max_items: int = 3) -> list[str]:
        candidates: list[str] = []

        if isinstance(value, list):
            for item in value:
                normalized = self._normalize_free_text(item, max_chars=180)
                if normalized:
                    candidates.append(normalized)

        elif isinstance(value, dict):
            for k, v in value.items():
                left = self._normalize_free_text(k, max_chars=120)
                right = self._normalize_free_text(v, max_chars=120) if isinstance(v, str) else None
                if left and right:
                    candidates.append(f"{left}: {right}")
                elif left:
                    candidates.append(left)

        else:
            normalized = self._normalize_free_text(value, max_chars=180)
            if normalized:
                candidates.append(normalized)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= max_items:
                break

        return deduped

    def _dedupe_list_items(
        self,
        items: list[dict[str, Any]],
        max_items: int,
    ) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                continue

            value = item.get("value")
            if not isinstance(value, str):
                continue

            key = re.sub(r"\s+", " ", value).strip().lower()
            if not key or key in seen:
                continue

            deduped.append(item)
            seen.add(key)

            if len(deduped) >= max_items:
                break

        return deduped

    def _extract_metrics_from_text(self, text: str) -> list[str]:
        if not text:
            return []

        keywords = [
            ("bleu", "BLEU"),
            ("rouge", "ROUGE"),
            ("f1", "F1"),
            ("accuracy", "accuracy"),
            ("precision", "precision"),
            ("recall", "recall"),
            ("map", "mAP"),
            ("mrr", "MRR"),
        ]

        normalized = text.lower()
        metrics: list[str] = []
        for needle, label in keywords:
            if re.search(rf"\\b{re.escape(needle)}\\b", normalized):
                metrics.append(label)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in metrics:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= 4:
                break

        return deduped

    def _has_meaningful_expected_payload(self, raw_result: dict[str, Any]) -> bool:
        problem = (((raw_result.get("problem") or {}).get("value")) if isinstance(raw_result.get("problem"), dict) else None)
        method = (((raw_result.get("method") or {}).get("value")) if isinstance(raw_result.get("method"), dict) else None)
        contributions = raw_result.get("contributions") or []
        limitations = raw_result.get("limitations") or []
        evaluation = ((raw_result.get("evaluation_setup") or {}).get("value") if isinstance(raw_result.get("evaluation_setup"), dict) else None) or {}

        if isinstance(problem, str) and problem.strip():
            return True
        if isinstance(method, str) and method.strip():
            return True
        if isinstance(contributions, list) and len(contributions) > 0:
            return True
        if isinstance(limitations, list) and len(limitations) > 0:
            return True

        if isinstance(evaluation, dict):
            datasets = evaluation.get("datasets") or []
            metrics = evaluation.get("metrics") or []
            benchmarks = evaluation.get("benchmarks") or []
            return bool(datasets or metrics or benchmarks)

        return False

    def _coerce_unexpected_schema_to_expected(self, raw_result: Any) -> dict[str, Any] | None:
        if not isinstance(raw_result, dict):
            return None

        main = raw_result.get("main") if isinstance(raw_result.get("main"), dict) else {}

        abstract = self._normalize_free_text(raw_result.get("abstract"), max_chars=260)
        introduction = self._normalize_free_text(raw_result.get("introduction"), max_chars=260)
        discussion = self._normalize_free_text(raw_result.get("discussion"), max_chars=260)

        methods = self._to_string_list(main.get("methods"), max_items=3)
        result_items = self._to_string_list(main.get("results"), max_items=3)

        problem_value = abstract or introduction
        method_value = methods[0] if methods else self._normalize_free_text(main.get("method"), max_chars=220)

        contributions_values: list[str] = []
        for item in methods + result_items:
            if item not in contributions_values:
                contributions_values.append(item)
            if len(contributions_values) >= 3:
                break

        limitations_values: list[str] = []
        if discussion and re.search(r"limitation|future|constraint|assumption|weakness|challenge", discussion, re.IGNORECASE):
            limitations_values.append(discussion)

        datasets: list[str] = []
        results_obj = main.get("results")
        if isinstance(results_obj, dict):
            for key in results_obj.keys():
                dataset = self._normalize_free_text(key, max_chars=80)
                if dataset and dataset not in datasets:
                    datasets.append(dataset)
                if len(datasets) >= 3:
                    break

        merged_text = " ".join([x for x in [abstract, introduction, discussion] if isinstance(x, str) and x])
        metrics = self._extract_metrics_from_text(merged_text)

        coerced = {
            "problem": {
                "value": problem_value,
                "evidence": [],
            },
            "method": {
                "value": method_value,
                "evidence": [],
            },
            "contributions": [
                {
                    "value": x,
                    "evidence": [],
                }
                for x in contributions_values
            ],
            "limitations": [
                {
                    "value": x,
                    "evidence": [],
                }
                for x in limitations_values
            ],
            "evaluation_setup": {
                "value": {
                    "datasets": datasets,
                    "metrics": metrics,
                    "benchmarks": [],
                },
                "evidence": [],
            },
        }

        if not self._has_meaningful_expected_payload(coerced):
            return None

        return coerced

    def _extract_tag_block(self, input_text: str, tag: str) -> str:
        if not isinstance(input_text, str) or not input_text.strip():
            return ""

        pattern = rf"\[{re.escape(tag)}\]\n(.*?)(?=\n\[[A-Z_]+\]\n|\Z)"
        match = re.search(pattern, input_text, flags=re.DOTALL)
        if not match:
            return ""

        return re.sub(r"\s+", " ", match.group(1)).strip()

    def _split_sentences(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        parts = re.split(r"(?<=[.!?])\s+", text)
        sentences: list[str] = []
        for part in parts:
            normalized = self._normalize_free_text(part, max_chars=220)
            if normalized:
                sentences.append(normalized)

        return sentences

    def _pick_sentence_by_keywords(self, sentences: list[str], keywords: list[str]) -> str | None:
        for sentence in sentences:
            lowered = sentence.lower()
            if any(keyword in lowered for keyword in keywords):
                return sentence
        return None

    def _extract_datasets_from_text(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        candidates: list[str] = []

        for match in re.findall(r"\b[A-Z]{2,}\s?\d{4}\b", text):
            dataset = self._normalize_free_text(match, max_chars=60)
            if dataset:
                candidates.append(dataset)

        known_dataset_tokens = [
            "ImageNet",
            "COCO",
            "SQuAD",
            "GLUE",
            "MNLI",
            "CIFAR-10",
            "CIFAR-100",
            "LibriSpeech",
            "WikiText",
            "WMT",
        ]

        lowered = text.lower()
        for token in known_dataset_tokens:
            if token.lower() in lowered:
                candidates.append(token)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= 3:
                break

        return deduped

    def _coerce_from_input_text(self, input_text: str) -> dict[str, Any] | None:
        abstract = self._extract_tag_block(input_text, "ABSTRACT")
        paper_text = self._extract_tag_block(input_text, "PAPER_TEXT")

        source_text = "\n".join([part for part in [abstract, paper_text] if part])
        if not source_text:
            return None

        abstract_sentences = self._split_sentences(abstract)
        paper_sentences = self._split_sentences(paper_text)
        all_sentences = abstract_sentences + paper_sentences
        if not all_sentences:
            return None

        problem_value = self._pick_sentence_by_keywords(
            all_sentences,
            ["problem", "task", "challenge", "goal", "aim"],
        ) or all_sentences[0]

        method_value = self._pick_sentence_by_keywords(
            all_sentences,
            [
                "propose",
                "present",
                "introduce",
                "develop",
                "method",
                "model",
                "approach",
                "framework",
                "architecture",
            ],
        )
        if method_value is None and len(all_sentences) > 1:
            method_value = all_sentences[1]

        contribution_keywords = [
            "propose",
            "present",
            "introduce",
            "contribution",
            "we show",
            "demonstrate",
            "achieve",
            "improve",
            "outperform",
            "state-of-the-art",
            "sota",
            "novel",
        ]

        contribution_candidates: list[str] = []
        for sentence in all_sentences:
            lowered = sentence.lower()
            if any(k in lowered for k in contribution_keywords):
                contribution_candidates.append(sentence)
            if len(contribution_candidates) >= 3:
                break

        limitation_keywords = [
            "limitation",
            "limitations",
            "future work",
            "constraint",
            "assumption",
            "weakness",
            "trade-off",
            "sensitive to",
            "depends on",
            "dependency",
            "fails on",
            "struggles with",
            "cannot",
            "does not",
            "expensive",
            "costly",
            "memory",
            "compute",
            "latency",
            "scalability",
        ]

        contrast_markers = ["however", "but", "yet", "although", "nevertheless"]

        limitation_candidates: list[str] = []
        for sentence in all_sentences:
            lowered = sentence.lower()
            has_limit_keyword = any(k in lowered for k in limitation_keywords)
            has_contrast_signal = any(k in lowered for k in contrast_markers)
            has_constraint_signal = any(
                k in lowered
                for k in [
                    "require",
                    "requires",
                    "resource",
                    "data",
                    "domain",
                    "robust",
                    "generalize",
                    "noisy",
                ]
            )

            if has_limit_keyword or (has_contrast_signal and has_constraint_signal):
                limitation_candidates.append(sentence)
            if len(limitation_candidates) >= 2:
                break

        datasets = self._extract_datasets_from_text(source_text)
        metrics = self._extract_metrics_from_text(source_text)

        coerced = {
            "problem": {
                "value": problem_value,
                "evidence": [],
            },
            "method": {
                "value": method_value,
                "evidence": [],
            },
            "contributions": [
                {
                    "value": item,
                    "evidence": [],
                }
                for item in contribution_candidates
            ],
            "limitations": [
                {
                    "value": item,
                    "evidence": [],
                }
                for item in limitation_candidates
            ],
            "evaluation_setup": {
                "value": {
                    "datasets": datasets,
                    "metrics": metrics,
                    "benchmarks": [],
                },
                "evidence": [],
            },
        }

        if not self._has_meaningful_expected_payload(coerced):
            return None

        return coerced

    def _enrich_missing_fields_from_input_text(
        self,
        normalized: dict[str, Any],
        input_text: str,
        pages: list[dict],
    ) -> dict[str, Any]:
        if not isinstance(input_text, str) or not input_text.strip():
            return normalized

        fallback = self._coerce_from_input_text(input_text)
        if not isinstance(fallback, dict):
            return normalized

        filled_keys: list[str] = []

        problem_field = normalized.get("problem")
        fallback_problem = self._normalize_scalar_field(fallback.get("problem"))
        if (
            isinstance(problem_field, dict)
            and not problem_field.get("value")
            and fallback_problem.get("value")
        ):
            normalized["problem"] = fallback_problem
            filled_keys.append("problem")

        method_field = normalized.get("method")
        fallback_method = self._normalize_scalar_field(fallback.get("method"))
        if (
            isinstance(method_field, dict)
            and not method_field.get("value")
            and fallback_method.get("value")
        ):
            normalized["method"] = fallback_method
            filled_keys.append("method")

        contributions = normalized.get("contributions")
        if not isinstance(contributions, list):
            contributions = []
        if len(contributions) == 0:
            fallback_contributions = self._normalize_list_field(
                fallback.get("contributions"),
                max_items=3,
            )
            if fallback_contributions:
                normalized["contributions"] = fallback_contributions
                filled_keys.append("contributions")

        limitations = normalized.get("limitations")
        if not isinstance(limitations, list):
            limitations = []
        if len(limitations) == 0:
            fallback_limitations = self._normalize_list_field(
                fallback.get("limitations"),
                max_items=2,
            )
            if fallback_limitations:
                normalized["limitations"] = fallback_limitations
                filled_keys.append("limitations")

        evaluation_setup = normalized.get("evaluation_setup")
        fallback_eval = self._normalize_evaluation_setup(fallback.get("evaluation_setup"), pages)
        if (
            isinstance(evaluation_setup, dict)
            and isinstance(fallback_eval, dict)
            and isinstance(evaluation_setup.get("value"), dict)
        ):
            current_value = evaluation_setup.get("value") or {}
            fallback_value = fallback_eval.get("value") or {}

            has_current_eval = bool(
                (current_value.get("datasets") or [])
                or (current_value.get("metrics") or [])
                or (current_value.get("benchmarks") or [])
            )
            has_fallback_eval = bool(
                (fallback_value.get("datasets") or [])
                or (fallback_value.get("metrics") or [])
                or (fallback_value.get("benchmarks") or [])
            )

            if not has_current_eval and has_fallback_eval:
                normalized["evaluation_setup"] = fallback_eval
                filled_keys.append("evaluation_setup")

        if filled_keys:
            logger.info(
                "[LLM NORMALIZE] Enriched missing fields from input_text: %s",
                ",".join(filled_keys),
            )

        return normalized

    def _extract_with_schema_retry_once(
        self,
        prompt: str,
        fallback_prompt: str | None,
        input_text: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            provider_result = self.provider.extract_metadata(
                prompt,
                fallback_prompt=fallback_prompt,
            )
        except Exception as e:
            logger.exception(
                "[LLM SERVICE] Provider call failed on primary extraction. error=%s",
                str(e),
            )

            degraded_provider_result = {
                "provider": "fallback",
                "model": getattr(self.provider, "ollama_model", None)
                or getattr(self.provider, "model", None)
                or "unknown",
                "raw_text": None,
                "usage": {},
            }

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SERVICE] Primary provider call failed; using deterministic fallback from input text.",
                )
                return degraded_provider_result, coerced_from_input

            logger.warning(
                "[LLM SERVICE] Primary provider call failed and no deterministic fallback available; using empty payload.",
            )
            return degraded_provider_result, {}

        raw_result = provider_result.get("result_json")

        if raw_result is None:
            raw_text = provider_result.get("raw_text")
            logger.error(
                "[LLM SERVICE] Invalid JSON from provider. raw_text=%s",
                raw_text[:2000] if raw_text else None,
            )
            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SERVICE] Invalid JSON from provider; using deterministic fallback from input text.",
                )
                return provider_result, coerced_from_input

            logger.warning(
                "[LLM SERVICE] Invalid JSON from provider and no deterministic fallback available; using empty payload.",
            )
            return provider_result, {}

        if self._has_expected_extraction_schema(raw_result):
            return provider_result, raw_result

        logger.warning(
            "[LLM SCHEMA] Unexpected schema from provider=%s model=%s keys=%s. Retrying once with schema-repair prompt.",
            provider_result.get("provider"),
            provider_result.get("model"),
            self._schema_keys_for_log(raw_result),
        )

        repair_prompt_gemini = self.prompt_builder.build_schema_repair_prompt_gemini(
            raw_result,
            input_text=input_text,
        )
        repair_prompt_gemma = self.prompt_builder.build_schema_repair_prompt_gemma(
            raw_result,
            input_text=input_text,
        )
        try:
            repaired_provider_result = self.provider.extract_metadata(
                repair_prompt_gemini,
                fallback_prompt=repair_prompt_gemma,
            )
        except Exception as e:
            logger.exception(
                "[LLM SCHEMA] Schema-repair provider call failed. error=%s",
                str(e),
            )

            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair provider failed; using local schema coercion from first response.",
                )
                return provider_result, coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair provider failed; using deterministic fallback from input text.",
                )
                return provider_result, coerced_from_input

            logger.warning(
                "[LLM SCHEMA] Schema-repair provider failed and no fallback available; using empty payload.",
            )
            return provider_result, {}

        repaired_raw_result = repaired_provider_result.get("result_json")

        if repaired_raw_result is None:
            raw_text = repaired_provider_result.get("raw_text")
            logger.error(
                "[LLM SCHEMA] Schema-repair retry returned invalid JSON. raw_text=%s",
                raw_text[:2000] if raw_text else None,
            )
            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry JSON invalid; using local schema coercion from first response.",
                )
                return provider_result, coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry JSON invalid; using deterministic fallback from input text.",
                )
                return repaired_provider_result, coerced_from_input

            logger.warning(
                "[LLM SCHEMA] Schema-repair retry JSON invalid and no fallback available; using empty payload.",
            )
            return repaired_provider_result, {}

        if not self._has_expected_extraction_schema(repaired_raw_result):
            coerced = self._coerce_unexpected_schema_to_expected(repaired_raw_result)
            if coerced is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry still non-standard; using local schema coercion.",
                )
                return repaired_provider_result, coerced

            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Retry non-standard; using local schema coercion from first response.",
                )
                return provider_result, coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Retry non-standard; using deterministic fallback from input text.",
                )
                return repaired_provider_result, coerced_from_input

            logger.error(
                "[LLM SCHEMA] Schema-repair retry failed. provider=%s model=%s keys=%s",
                repaired_provider_result.get("provider"),
                repaired_provider_result.get("model"),
                self._schema_keys_for_log(repaired_raw_result),
            )
            logger.warning(
                "[LLM SCHEMA] Retry exhausted with non-standard schema; using empty payload to avoid hard failure.",
            )
            return repaired_provider_result, {}

        logger.info(
            "[LLM SCHEMA] Schema-repair retry succeeded. provider=%s model=%s",
            repaired_provider_result.get("provider"),
            repaired_provider_result.get("model"),
        )

        return repaired_provider_result, repaired_raw_result

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
            setattr(cached_run, "cache_hit", True)

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
            prompt_gemini = self.prompt_builder.build_extraction_prompt_gemini(input_text)
            prompt_gemma = self.prompt_builder.build_extraction_prompt_gemma(input_text)
            provider_result, raw_result = self._extract_with_schema_retry_once(
                prompt=prompt_gemini,
                fallback_prompt=prompt_gemma,
                input_text=input_text,
            )
            raw_result = self._apply_semantic_correction(raw_result, full_text)

            result_json = self._normalize_result(
                raw_result,
                pages,
                input_text=input_text,
            )

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
            setattr(run, "cache_hit", False)

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

        # 🔥 1. ưu tiên docling markdown
        for paper in canonical.papers:
            md_path = getattr(paper, "docling_markdown_storage_path", None)
            if not md_path:
                continue

            try:
                md_bytes = storage.download_by_storage_path(md_path)
                markdown = md_bytes.decode("utf-8")

                text_len = len((markdown or "").strip())

                logger.info(
                    "[LLM SERVICE] Loaded DOCILING markdown for canonical=%s paper_id=%s text_len=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    text_len,
                )

                if text_len > 0:
                    # ⚠️ docling chưa có page mapping → để empty hoặc simple mapping
                    pages_path = getattr(paper, "page_text_json_storage_path", None)

                    pages = []

                    if pages_path:
                        try:
                            pages_bytes = storage.download_by_storage_path(pages_path)
                            pages = json.loads(pages_bytes.decode("utf-8"))

                            logger.info(
                                "[LLM SERVICE] Loaded pages.json for canonical=%s paper_id=%s pages=%s",
                                canonical.id,
                                getattr(paper, "id", None),
                                len(pages),
                            )
                        except Exception as e:
                            logger.warning(
                                "[LLM SERVICE] Failed to load pages.json canonical=%s paper_id=%s error=%s",
                                canonical.id,
                                getattr(paper, "id", None),
                                str(e),
                            )

                    return markdown, pages

            except Exception as e:
                logger.warning(
                    "[LLM SERVICE] Failed to load docling markdown for canonical=%s paper_id=%s error=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    str(e),
                )

        # 🔽 2. fallback pdfplumber (giữ lại)
        logger.warning(
            "[LLM SERVICE] Falling back to pdfplumber for canonical=%s",
            canonical.id,
        )

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

                if text_len > 0:
                    return full_text, pages

            except Exception as e:
                logger.warning(
                    "[LLM SERVICE] Failed fallback pdfplumber canonical=%s error=%s",
                    canonical.id,
                    str(e),
                )

            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        return None, []

    def _is_placeholder_text(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False

        normalized = re.sub(r"\s+", " ", value).strip().lower()
        if not normalized:
            return False

        placeholders = {
            "string",
            "string | null",
            "integer",
            "integer | null",
            "number",
            "number | null",
            "boolean",
            "boolean | null",
            "null",
            "none",
            "n/a",
            "na",
            "unknown",
            "placeholder",
            "tbd",
            "to be determined",
        }

        if normalized in placeholders:
            return True

        if normalized.startswith("<") and normalized.endswith(">"):
            return True

        return False

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
            if self._is_placeholder_text(snippet):
                continue

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

    def _build_fallback_evidence_from_text(
        self,
        text: str,
        pages: list[dict],
    ) -> list[dict[str, Any]]:
        if not isinstance(text, str):
            return []

        snippet = re.sub(r"\s+", " ", text).strip()
        if not snippet or self._is_placeholder_text(snippet):
            return []

        if len(snippet) > 180:
            cut = snippet[:180]
            last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
            if last_stop > 80:
                snippet = cut[:last_stop].strip()
            else:
                snippet = cut.strip()

        if not snippet:
            return []

        return [
            {
                "snippet": snippet,
                "page": self._match_snippet_to_page(snippet, pages),
                "section": None,
            }
        ]

    def _normalize_scalar_field(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {"value": None, "evidence": []}

        if isinstance(raw, str):
            value = raw.strip() or None
            if value and self._is_placeholder_text(value):
                value = None
            return {"value": value, "evidence": []}

        if not isinstance(raw, dict):
            return {"value": None, "evidence": []}

        value = raw.get("value")
        if not isinstance(value, str):
            value = None
        else:
            value = value.strip() or None
            if value and self._is_placeholder_text(value):
                value = None

        evidence = self._normalize_evidence(raw.get("evidence"))

        return {
            "value": value,
            "evidence": evidence,
        }

    def _normalize_list_field(
        self,
        raw: Any,
        max_items: int = 3,
    ) -> list[dict[str, Any]]:
        if raw is None:
            return []

        normalized_items: list[dict[str, Any]] = []

        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str):
                    value = x.strip()
                    if not value or self._is_placeholder_text(value):
                        continue

                    normalized_items.append(
                        {
                            "value": value,
                            "evidence": [],
                        }
                    )
                    continue

                if not isinstance(x, dict):
                    continue

                value = x.get("value")
                if not isinstance(value, str) or not value.strip():
                    continue

                if self._is_placeholder_text(value):
                    continue

                evidence = self._normalize_evidence(x.get("evidence"))
                normalized_items.append({
                    "value": value.strip(),
                    "evidence": evidence,
                })

            return self._dedupe_list_items(normalized_items, max_items=max_items)

        if not isinstance(raw, dict):
            return []

        # backward-compatible old format:
        # {"items": ["a", "b"], "evidence": [...]}
        raw_items = raw.get("items")
        if raw_items is None:
            raw_items = raw.get("value")

        if not isinstance(raw_items, list):
            return []

        evidence = self._normalize_evidence(raw.get("evidence"))
        for x in raw_items:
            if not isinstance(x, str) or not x.strip():
                continue

            if self._is_placeholder_text(x):
                continue

            normalized_items.append({
                "value": x.strip(),
                "evidence": evidence,
            })

        return self._dedupe_list_items(normalized_items, max_items=max_items)

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

        datasets = [
            x.strip()
            for x in value.get("datasets", [])
            if isinstance(x, str) and x.strip() and not self._is_placeholder_text(x)
        ]
        metrics = [
            x.strip()
            for x in value.get("metrics", [])
            if isinstance(x, str) and x.strip() and not self._is_placeholder_text(x)
        ]
        benchmarks = [
            x.strip()
            for x in value.get("benchmarks", [])
            if isinstance(x, str) and x.strip() and not self._is_placeholder_text(x)
        ]

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

    def _ensure_evidence_from_values(
        self,
        normalized: dict[str, Any],
        pages: list[dict],
    ) -> dict[str, Any]:
        for scalar_key in ["problem", "method"]:
            field = normalized.get(scalar_key) or {}
            value = field.get("value") if isinstance(field, dict) else None
            evidence = field.get("evidence") if isinstance(field, dict) else []
            if isinstance(value, str) and value.strip() and (not isinstance(evidence, list) or len(evidence) == 0):
                field["evidence"] = self._build_fallback_evidence_from_text(value, pages)

        for list_key in ["contributions", "limitations"]:
            items = normalized.get(list_key)
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                value = item.get("value")
                evidence = item.get("evidence")
                if isinstance(value, str) and value.strip() and (not isinstance(evidence, list) or len(evidence) == 0):
                    item["evidence"] = self._build_fallback_evidence_from_text(value, pages)

        evaluation_setup = normalized.get("evaluation_setup")
        if isinstance(evaluation_setup, dict):
            evidence = evaluation_setup.get("evidence")
            value = evaluation_setup.get("value")

            if (not isinstance(evidence, list) or len(evidence) == 0) and isinstance(value, dict):
                tokens: list[str] = []
                for key in ["datasets", "metrics", "benchmarks"]:
                    arr = value.get(key)
                    if isinstance(arr, list):
                        tokens.extend([x for x in arr if isinstance(x, str) and x.strip()])

                if tokens:
                    evaluation_setup["evidence"] = self._build_fallback_evidence_from_text(
                        "; ".join(tokens),
                        pages,
                    )

        return normalized

    def _normalize_result(
        self,
        raw: dict[str, Any] | None,
        pages: list[dict],
        input_text: str = "",
    ) -> dict[str, Any]:
        raw = raw or {}

        normalized = {
            "problem": self._normalize_scalar_field(raw.get("problem")),
            "method": self._normalize_scalar_field(raw.get("method")),
            "contributions": self._normalize_list_field(raw.get("contributions"), max_items=3),
            "limitations": self._normalize_list_field(raw.get("limitations"), max_items=2),
            "evaluation_setup": self._normalize_evaluation_setup(raw.get("evaluation_setup"), pages),
        }
        normalized = self._enrich_missing_fields_from_input_text(normalized, input_text, pages)
        normalized = self._ensure_evidence_from_values(normalized, pages)
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
        field_obj: Any,
        pages: list[dict],
    ) -> Any:
        if not field_obj:
            return field_obj

        if isinstance(field_obj, list):
            normalized_items: list[dict[str, Any]] = []

            for item in field_obj:
                if not isinstance(item, dict):
                    continue

                evidences = item.get("evidence") or []
                for ev in evidences:
                    if ev.get("page") is None:
                        matched_page = self._match_snippet_to_page(
                            ev.get("snippet", ""),
                            pages,
                        )
                        if matched_page is not None:
                            ev["page"] = matched_page

                normalized_items.append(item)

            return normalized_items

        if isinstance(field_obj, dict):
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

        return field_obj