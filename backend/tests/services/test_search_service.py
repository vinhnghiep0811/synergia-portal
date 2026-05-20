import unittest
from types import SimpleNamespace

from app.services.search_service import SearchService


class SearchServiceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(SearchService)

    def test_semantic_evidence_snippet_prefers_query_relevant_sentence(self) -> None:
        content = (
            "This opening sentence is intentionally long and generic. " * 12
            + "The proposed transformer uses attention mechanisms for sequence transduction. "
            + "This final sentence is unrelated."
        )

        snippet = self.service._semantic_evidence_snippet(
            "transformer attention sequence",
            content,
            window=180,
        )

        self.assertIn("transformer uses attention", snippet)
        self.assertIn("sequence transduction", snippet)
        self.assertLessEqual(len(snippet), 186)

    def test_optimization_query_prefers_technical_method_chunks(self) -> None:
        generation_chunk = SimpleNamespace(
            section="Generation",
            section_full_path="Generation",
            section_type="other",
            content=(
                "We use the common left-to-right beam-search method for sequence "
                "generation and rank hypotheses by likelihood."
            ),
        )
        abstract_chunk = SimpleNamespace(
            section="Abstract",
            section_full_path="Abstract",
            section_type="abstract",
            content=(
                "The model improves translation task results and reduces training "
                "costs compared with previous systems."
            ),
        )
        query = "Optimization techniques for sequence-to-sequence translation systems"

        self.assertEqual(self.service._detect_query_type(query), "technical_method")
        self.assertGreater(
            self.service._query_aware_boost(query, generation_chunk),
            self.service._query_aware_boost(query, abstract_chunk),
        )
        self.assertGreater(
            self.service._lexical_relevance_boost(query, generation_chunk),
            self.service._lexical_relevance_boost(query, abstract_chunk),
        )


if __name__ == "__main__":
    unittest.main()
