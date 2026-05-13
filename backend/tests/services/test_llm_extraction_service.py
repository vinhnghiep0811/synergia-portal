import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.llm_extraction_service import LLMExtractionService


def make_service() -> LLMExtractionService:
    return object.__new__(LLMExtractionService)


def make_expected_schema_payload(problem: str = "problem statement") -> dict:
    return {
        "problem": {"value": problem, "evidence": []},
        "method": {"value": "method summary", "evidence": []},
        "contributions": [{"value": "contribution", "evidence": []}],
        "limitations": [{"value": "limitation", "evidence": []}],
        "evaluation_setup": {
            "value": {"datasets": ["ImageNet"], "metrics": ["F1"], "benchmarks": []},
            "evidence": [{"snippet": "ImageNet with F1", "page": 1, "section": "Evaluation"}],
        },
    }


class ExpectedSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_has_expected_extraction_schema_returns_true_for_required_keys(self) -> None:
        raw = {
            "problem": {"value": "p", "evidence": []},
            "method": {"value": "m", "evidence": []},
            "contributions": [],
            "limitations": [],
            "evaluation_setup": {"value": {"datasets": [], "metrics": [], "benchmarks": []}, "evidence": []},
        }

        result = self.service._has_expected_extraction_schema(raw)

        self.assertTrue(result)

    def test_has_expected_extraction_schema_returns_false_when_missing_key(self) -> None:
        raw = {
            "problem": {"value": "p", "evidence": []},
            "method": {"value": "m", "evidence": []},
            "contributions": [],
            "limitations": [],
        }

        result = self.service._has_expected_extraction_schema(raw)

        self.assertFalse(result)

    def test_schema_keys_for_log_sorts_keys_for_dict(self) -> None:
        raw = {"z": 1, "a": 2, "m": 3}

        result = self.service._schema_keys_for_log(raw)

        self.assertEqual(result, "a,m,z")


class NormalizeFreeTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_normalize_free_text_returns_none_for_placeholder_value(self) -> None:
        result = self.service._normalize_free_text("N/A")

        self.assertIsNone(result)

    def test_normalize_free_text_collapses_whitespace_and_truncates(self) -> None:
        text = "  This    is a sentence. " + ("word " * 80)

        result = self.service._normalize_free_text(text, max_chars=90)

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected normalized text, got None")
        self.assertLessEqual(len(result), 90)
        self.assertNotIn("  ", result)

    def test_to_string_list_deduplicates_and_limits_items(self) -> None:
        value = ["Alpha", "alpha", "Beta", "Gamma", "Delta"]

        result = self.service._to_string_list(value, max_items=3)

        self.assertEqual(result, ["Alpha", "Beta", "Gamma"])

    def test_extract_metrics_from_text_detects_supported_metrics(self) -> None:
        text = "We report BLEU, F1, precision and recall on experiments."

        result = self.service._extract_metrics_from_text(text)

        self.assertIn("BLEU", result)
        self.assertIn("F1", result)
        self.assertIn("precision", result)
        self.assertIn("recall", result)


class CoerceUnexpectedSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_coerce_unexpected_schema_builds_expected_shape(self) -> None:
        raw = {
            "abstract": "This paper addresses a challenging multimodal retrieval problem.",
            "discussion": "A key limitation is the large memory footprint for long documents.",
            "main": {
                "methods": ["We introduce a dual-encoder architecture with late fusion."],
                "results": {
                    "ImageNet": "Improves retrieval precision over prior work.",
                },
            },
        }

        result = self.service._coerce_unexpected_schema_to_expected(raw)

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected coerced schema, got None")
        self.assertIn("problem", result)
        self.assertIn("method", result)
        self.assertIn("contributions", result)
        self.assertIn("limitations", result)
        self.assertIn("evaluation_setup", result)
        self.assertEqual(result["problem"]["value"], raw["abstract"])
        self.assertEqual(
            result["method"]["value"],
            "We introduce a dual-encoder architecture with late fusion.",
        )
        self.assertGreaterEqual(len(result["contributions"]), 1)
        self.assertGreaterEqual(len(result["limitations"]), 1)
        self.assertIn("ImageNet", result["evaluation_setup"]["value"]["datasets"])

    def test_coerce_unexpected_schema_returns_none_when_payload_empty(self) -> None:
        raw = {"main": {}}

        result = self.service._coerce_unexpected_schema_to_expected(raw)

        self.assertIsNone(result)


class SchemaRepairRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_extract_with_schema_retry_once_uses_input_fallback_when_primary_call_fails(self) -> None:
        self.service.provider = Mock()
        self.service.provider.ollama_model = None
        self.service.provider.model = "gemma-local"
        self.service.provider.extract_metadata.side_effect = RuntimeError("provider down")
        fallback_payload = make_expected_schema_payload(problem="Recovered from input")
        self.service._coerce_from_input_text = Mock(return_value=fallback_payload)

        provider_result, raw_result = self.service._extract_with_schema_retry_once(
            prompt="primary prompt",
            fallback_prompt="fallback prompt",
            input_text="[ABSTRACT]\nRecovered from input\n",
        )

        self.assertEqual(provider_result["provider"], "fallback")
        self.assertEqual(provider_result["model"], "gemma-local")
        self.assertEqual(provider_result["usage"], {})
        self.assertIs(raw_result, fallback_payload)

    def test_extract_with_schema_retry_once_returns_repaired_payload_when_retry_succeeds(self) -> None:
        self.service.provider = Mock()
        self.service.prompt_builder = Mock()
        self.service.prompt_builder.build_schema_repair_prompt_gemini.return_value = "repair gemini"
        self.service.prompt_builder.build_schema_repair_prompt_gemma.return_value = "repair gemma"

        initial_provider_result = {
            "provider": "gemini",
            "model": "gemini-1",
            "result_json": {"legacy": {"field": "value"}},
        }
        repaired_payload = make_expected_schema_payload(problem="Repaired problem")
        repaired_provider_result = {
            "provider": "gemini",
            "model": "gemini-1-repair",
            "result_json": repaired_payload,
        }
        self.service.provider.extract_metadata.side_effect = [
            initial_provider_result,
            repaired_provider_result,
        ]

        provider_result, raw_result = self.service._extract_with_schema_retry_once(
            prompt="primary prompt",
            fallback_prompt="fallback prompt",
            input_text="input text",
        )

        self.assertIs(provider_result, repaired_provider_result)
        self.assertIs(raw_result, repaired_payload)
        self.service.prompt_builder.build_schema_repair_prompt_gemini.assert_called_once_with(
            initial_provider_result["result_json"],
            input_text="input text",
        )
        self.service.prompt_builder.build_schema_repair_prompt_gemma.assert_called_once_with(
            initial_provider_result["result_json"],
            input_text="input text",
        )

    def test_extract_with_schema_retry_once_uses_initial_coercion_when_repair_call_fails(self) -> None:
        self.service.provider = Mock()
        self.service.prompt_builder = Mock()
        self.service.prompt_builder.build_schema_repair_prompt_gemini.return_value = "repair gemini"
        self.service.prompt_builder.build_schema_repair_prompt_gemma.return_value = "repair gemma"

        first_payload = {"unexpected": {"shape": True}}
        initial_provider_result = {
            "provider": "gemini",
            "model": "gemini-1",
            "result_json": first_payload,
        }
        self.service.provider.extract_metadata.side_effect = [
            initial_provider_result,
            RuntimeError("repair failed"),
        ]
        coerced_payload = make_expected_schema_payload(problem="Coerced from first payload")
        self.service._coerce_unexpected_schema_to_expected = Mock(return_value=coerced_payload)
        self.service._coerce_from_input_text = Mock(
            side_effect=AssertionError("Should not reach input-text fallback in this branch.")
        )

        provider_result, raw_result = self.service._extract_with_schema_retry_once(
            prompt="primary prompt",
            fallback_prompt="fallback prompt",
            input_text="input text",
        )

        self.assertIs(provider_result, initial_provider_result)
        self.assertIs(raw_result, coerced_payload)
        self.service._coerce_unexpected_schema_to_expected.assert_called_once_with(first_payload)

    def test_extract_with_schema_retry_once_uses_input_fallback_when_repair_json_invalid(self) -> None:
        self.service.provider = Mock()
        self.service.prompt_builder = Mock()
        self.service.prompt_builder.build_schema_repair_prompt_gemini.return_value = "repair gemini"
        self.service.prompt_builder.build_schema_repair_prompt_gemma.return_value = "repair gemma"

        initial_provider_result = {
            "provider": "gemini",
            "model": "gemini-1",
            "result_json": {"legacy": "shape"},
        }
        repaired_provider_result = {
            "provider": "gemini",
            "model": "gemini-1-repair",
            "result_json": None,
            "raw_text": "not-json",
        }
        self.service.provider.extract_metadata.side_effect = [
            initial_provider_result,
            repaired_provider_result,
        ]

        self.service._coerce_unexpected_schema_to_expected = Mock(return_value=None)
        fallback_payload = make_expected_schema_payload(problem="Fallback from input text")
        self.service._coerce_from_input_text = Mock(return_value=fallback_payload)

        provider_result, raw_result = self.service._extract_with_schema_retry_once(
            prompt="primary prompt",
            fallback_prompt="fallback prompt",
            input_text="input text",
        )

        self.assertIs(provider_result, repaired_provider_result)
        self.assertIs(raw_result, fallback_payload)
        self.service._coerce_from_input_text.assert_called_once_with("input text")


class NormalizeResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_normalize_result_keeps_schema_valid_with_evidence(self) -> None:
        pages = [
            {
                "page": 1,
                "text": (
                    "This paper tackles relation extraction. "
                    "We propose a graph encoder. "
                    "Improves F1 on benchmark. "
                    "Requires GPU memory. "
                    "Evaluation on ImageNet with F1 metric."
                ),
            }
        ]
        raw = {
            "problem": "This paper tackles relation extraction.",
            "method": {"value": "We propose a graph encoder.", "evidence": []},
            "contributions": ["Improves F1 on benchmark."],
            "limitations": [{"value": "Requires GPU memory.", "evidence": []}],
            "evaluation_setup": {
                "value": {
                    "datasets": ["ImageNet"],
                    "metrics": ["F1"],
                    "benchmarks": [],
                },
                "evidence": [
                    {
                        "snippet": "Evaluation on ImageNet with F1 metric.",
                        "page": 1,
                        "section": "Evaluation",
                    }
                ],
            },
        }

        normalized = self.service._normalize_result(raw, pages=pages, input_text="")

        self.assertEqual(normalized["problem"]["value"], "This paper tackles relation extraction.")
        self.assertGreater(len(normalized["problem"]["evidence"]), 0)
        self.assertGreater(len(normalized["method"]["evidence"]), 0)
        self.assertGreater(len(normalized["contributions"]), 0)
        self.assertGreater(len(normalized["contributions"][0]["evidence"]), 0)
        self.assertEqual(normalized["evaluation_setup"]["value"]["datasets"], ["ImageNet"])
        self.assertGreater(len(normalized["evaluation_setup"]["evidence"]), 0)

    def test_normalize_list_field_drops_placeholder_and_dedupes(self) -> None:
        raw = [
            "First contribution",
            "N/A",
            "first contribution",
            {"value": "Second contribution", "evidence": []},
        ]

        result = self.service._normalize_list_field(raw, max_items=5)

        values = [item["value"] for item in result]
        self.assertEqual(values, ["First contribution", "Second contribution"])

    def test_normalize_evaluation_setup_drops_content_when_missing_evidence(self) -> None:
        raw = {
            "value": {
                "datasets": ["ImageNet"],
                "metrics": ["F1"],
                "benchmarks": [],
            },
            "evidence": [],
        }

        result = self.service._normalize_evaluation_setup(raw, pages=[])

        self.assertEqual(result["value"]["datasets"], [])
        self.assertEqual(result["value"]["metrics"], [])
        self.assertEqual(result["value"]["benchmarks"], [])
        self.assertEqual(result["evidence"], [])

    def test_normalize_evidence_filters_numeric_dump(self) -> None:
        raw_evidence = [
            {
                "snippet": "12345 67890 11111 22222 33333 44444 55555 66666",
                "page": 2,
                "section": "Table 1",
            },
            {
                "snippet": "We propose a practical method with robust performance.",
                "page": 1,
                "section": "Method",
            },
        ]

        result = self.service._normalize_evidence(raw_evidence)

        self.assertEqual(len(result), 1)
        self.assertIn("practical method", result[0]["snippet"].lower())

    def test_normalize_evidence_repairs_spacing_truncates_and_normalizes_metadata_types(self) -> None:
        long_snippet = (
            "ThisMethod2achievesHighAccuracy,despite noisy data in production pipelines. "
            + ("extra token " * 40)
        )
        raw_evidence = [
            {
                "snippet": "<string>",
                "page": 2,
                "section": "Placeholder",
            },
            {
                "snippet": long_snippet,
                "page": "1",
                "section": 99,
            },
        ]

        result = self.service._normalize_evidence(raw_evidence)

        self.assertEqual(len(result), 1)
        self.assertIn("Method 2 achieves High Accuracy, despite noisy data", result[0]["snippet"])
        self.assertLessEqual(len(result[0]["snippet"]), 180)
        self.assertIsNone(result[0]["page"])
        self.assertIsNone(result[0]["section"])

    def test_normalize_evaluation_setup_uses_inferred_evidence_when_available(self) -> None:
        self.service._infer_evaluation_evidence_from_pages = Mock(
            return_value=[{"snippet": "Evaluation on ImageNet with F1", "page": 1, "section": "Evaluation"}]
        )
        raw = {
            "value": {
                "datasets": ["ImageNet"],
                "metrics": ["F1"],
                "benchmarks": [],
            },
            "evidence": [],
        }

        result = self.service._normalize_evaluation_setup(
            raw,
            pages=[{"page": 1, "text": "Evaluation on ImageNet with F1"}],
        )

        self.assertEqual(result["value"]["datasets"], ["ImageNet"])
        self.assertEqual(result["value"]["metrics"], ["F1"])
        self.assertEqual(result["evidence"][0]["page"], 1)
        self.assertEqual(result["evidence"][0]["section"], "Evaluation")

    def test_normalize_result_enriches_missing_fields_from_input_text(self) -> None:
        pages = [
            {
                "page": 1,
                "text": (
                    "This paper addresses a retrieval problem. "
                    "We propose a dual encoder architecture. "
                    "It improves F1 on ImageNet benchmark but requires large memory."
                ),
            }
        ]
        raw = {
            "problem": None,
            "method": None,
            "contributions": [],
            "limitations": [],
            "evaluation_setup": {
                "value": {"datasets": [], "metrics": [], "benchmarks": []},
                "evidence": [],
            },
        }
        input_text = (
            "[ABSTRACT]\n"
            "This paper addresses a retrieval problem.\n"
            "[PAPER_TEXT]\n"
            "We propose a dual encoder architecture. "
            "It improves F1 on ImageNet benchmark but requires large memory.\n"
        )

        normalized = self.service._normalize_result(raw, pages=pages, input_text=input_text)

        self.assertEqual(normalized["problem"]["value"], "This paper addresses a retrieval problem.")
        self.assertEqual(normalized["method"]["value"], "We propose a dual encoder architecture.")
        self.assertGreater(len(normalized["problem"]["evidence"]), 0)
        self.assertEqual(normalized["problem"]["evidence"][0]["page"], 1)
        self.assertGreater(len(normalized["contributions"]), 0)
        self.assertIn("evaluation_setup", normalized)


class CacheDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_run_for_canonical_document_returns_cached_run(self) -> None:
        canonical_id = uuid4()
        canonical = Mock(id=canonical_id)
        cached_run = Mock()

        self.service.repo = Mock()
        self.service.repo.get_latest_completed_by_canonical_document_id.return_value = cached_run
        self.service._get_canonical_or_raise = Mock(return_value=canonical)
        self.service._create_running_extraction_run = Mock(
            side_effect=AssertionError("Cache hit should return before creating a new run.")
        )

        result = self.service.run_for_canonical_document(canonical_id)

        self.assertIs(result, cached_run)
        self.assertTrue(getattr(result, "cache_hit", False))
        self.service._get_canonical_or_raise.assert_called_once_with(canonical_id)
        self.service.repo.get_latest_completed_by_canonical_document_id.assert_called_once_with(canonical_id)

    def test_run_for_canonical_document_uses_resolved_canonical_id_for_cache_lookup(self) -> None:
        requested_id = uuid4()
        resolved_id = uuid4()
        canonical = Mock(id=resolved_id)
        cached_run = Mock()

        self.service.repo = Mock()
        self.service.repo.get_latest_completed_by_canonical_document_id.return_value = cached_run
        self.service._get_canonical_or_raise = Mock(return_value=canonical)
        self.service._create_running_extraction_run = Mock(
            side_effect=AssertionError("Cache hit should return before creating a new run.")
        )

        self.service.run_for_canonical_document(requested_id)

        self.service.repo.get_latest_completed_by_canonical_document_id.assert_called_once_with(resolved_id)

    def test_run_for_canonical_document_cache_miss_creates_and_completes_run(self) -> None:
        requested_id = uuid4()
        resolved_id = uuid4()
        canonical = Mock(id=resolved_id)
        running_run = Mock()
        completed_run = Mock()
        provider_result = {
            "provider": "gemini",
            "model": "gemini-1.5-pro",
            "raw_text": '{"ok": true}',
            "usage": {"prompt_tokens": 101, "completion_tokens": 202},
        }
        normalized_result = make_expected_schema_payload(problem="Extracted problem")

        self.service.db = Mock()
        self.service.repo = Mock()
        self.service.repo.get_latest_completed_by_canonical_document_id.return_value = None
        self.service.repo.mark_completed.return_value = completed_run
        self.service._get_canonical_or_raise = Mock(return_value=canonical)
        self.service._create_running_extraction_run = Mock(return_value=running_run)
        self.service._load_full_text_for_canonical = Mock(return_value=("A" * 600, []))
        self.service.input_builder = Mock()
        self.service.input_builder.build.return_value = "input text"
        self.service.prompt_builder = Mock()
        self.service.prompt_builder.build_extraction_prompt_gemini.return_value = "gemini prompt"
        self.service.prompt_builder.build_extraction_prompt_gemma.return_value = "gemma prompt"
        self.service._extract_with_schema_retry_once = Mock(
            return_value=(provider_result, {"result": "raw"})
        )
        self.service._apply_semantic_correction = Mock(return_value={"result": "raw"})
        self.service._normalize_result = Mock(return_value=normalized_result)

        result = self.service.run_for_canonical_document(requested_id)

        self.assertIs(result, completed_run)
        self.assertFalse(getattr(result, "cache_hit", True))
        self.service.repo.get_latest_completed_by_canonical_document_id.assert_called_once_with(resolved_id)
        self.service._create_running_extraction_run.assert_called_once_with(resolved_id)
        self.service.repo.mark_completed.assert_called_once()
        mark_completed_kwargs = self.service.repo.mark_completed.call_args.kwargs
        self.assertEqual(mark_completed_kwargs["token_input"], 101)
        self.assertEqual(mark_completed_kwargs["token_output"], 202)
        self.assertEqual(mark_completed_kwargs["result_json"], normalized_result)
        self.assertEqual(mark_completed_kwargs["problem_statement"], normalized_result["problem"])
        self.service.repo.set_latest_for_canonical_document.assert_called_once_with(canonical, completed_run)

    def test_run_for_canonical_document_marks_failed_when_text_is_insufficient(self) -> None:
        requested_id = uuid4()
        resolved_id = uuid4()
        canonical = Mock(id=resolved_id)
        running_run = Mock()

        self.service.db = Mock()
        self.service.repo = Mock()
        self.service.repo.get_latest_completed_by_canonical_document_id.return_value = None
        self.service._get_canonical_or_raise = Mock(return_value=canonical)
        self.service._create_running_extraction_run = Mock(return_value=running_run)
        self.service._load_full_text_for_canonical = Mock(return_value=("too short", []))

        with self.assertRaises(ValueError) as ctx:
            self.service.run_for_canonical_document(requested_id)

        self.assertIn("Insufficient text for LLM extraction", str(ctx.exception))
        self.service.repo.mark_completed.assert_not_called()
        self.service.repo.set_latest_for_canonical_document.assert_not_called()
        self.service.repo.mark_failed.assert_called_once()
        mark_failed_args, mark_failed_kwargs = self.service.repo.mark_failed.call_args
        self.assertIs(mark_failed_args[0], running_run)
        self.assertIn("Insufficient text for LLM extraction", mark_failed_kwargs["error_message"])
        self.assertIsNone(mark_failed_kwargs["raw_llm_response"])
        self.assertEqual(canonical.extraction_cache_status, "failed")
        self.service.db.add.assert_called_once_with(canonical)
        self.service.db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
