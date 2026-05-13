import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.llm_extraction_service import LLMExtractionService


def make_service() -> LLMExtractionService:
    return object.__new__(LLMExtractionService)


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


if __name__ == "__main__":
    unittest.main()
