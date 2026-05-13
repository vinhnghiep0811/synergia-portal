"""Integration tests: LLM extraction and schema handling."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


def valid_payload() -> dict:
    return {
        "problem": {"value": "Problem statement", "evidence": []},
        "method": {"value": "Main method", "evidence": []},
        "contributions": [{"value": "Contribution", "evidence": []}],
        "limitations": [{"value": "Limitation", "evidence": []}],
        "evaluation_setup": {
            "value": {
                "datasets": ["Dataset A"],
                "metrics": ["F1"],
                "benchmarks": [],
            },
            "evidence": [],
        },
    }


class LlmExtractionIntegrationTests(IntegrationEphemeralTestCase):
    def test_llm_extraction_persists_normalized_result(self) -> None:
        paper_id = self.workflow.upload_pdf("llm.pdf", b"%PDF-1.4\nllm")
        canonical_key = self.workflow.parse_and_map(paper_id, "DOI: 10.4242/llm")["canonical_key"]

        normalized = self.workflow.run_llm_extraction(canonical_key, valid_payload())
        cached = self.workflow.get_cached_extraction(canonical_key)

        self.assertIn("problem", normalized)
        self.assertIsNotNone(cached)
        self.assertIn("method", cached)

    def test_llm_extraction_rejects_invalid_schema(self) -> None:
        paper_id = self.workflow.upload_pdf("bad.pdf", b"%PDF-1.4\nbad")
        canonical_key = self.workflow.parse_and_map(paper_id, "DOI: 10.4242/bad")["canonical_key"]

        with self.assertRaises(ValueError):
            self.workflow.run_llm_extraction(canonical_key, {"problem": "missing keys"})

    def test_cache_lookup_returns_none_on_miss(self) -> None:
        self.assertIsNone(self.workflow.get_cached_extraction("missing-key"))

    def test_same_canonical_overwrites_cache_with_latest_result(self) -> None:
        paper_id = self.workflow.upload_pdf("v.pdf", b"%PDF-1.4\nv")
        key = self.workflow.parse_and_map(paper_id, "DOI: 10.4242/versioned")["canonical_key"]

        first = valid_payload()
        second = valid_payload()
        second["method"]["value"] = "Updated method"
        self.workflow.run_llm_extraction(key, first)
        self.workflow.run_llm_extraction(key, second)

        cached = self.workflow.get_cached_extraction(key)
        self.assertEqual(cached["method"]["value"], "Updated method")
