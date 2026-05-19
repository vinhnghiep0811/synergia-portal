import unittest

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


if __name__ == "__main__":
    unittest.main()
