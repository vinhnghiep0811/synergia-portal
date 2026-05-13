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


if __name__ == "__main__":
    unittest.main()
