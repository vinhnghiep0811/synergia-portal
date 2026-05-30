import unittest
from types import SimpleNamespace

from app.services.semantic_scholar_service import SemanticScholarService


class SemanticScholarDoiValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(SemanticScholarService)

    def test_doi_match_is_rejected_when_titles_are_unrelated(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi="10.5555/wrong",
            title_candidate="Attention Is All You Need",
        )
        paper_data = {"title": "Deep Residual Learning for Image Recognition"}

        result = self.service._is_doi_title_mismatch(canonical, paper_data)

        self.assertTrue(result)

    def test_doi_match_is_kept_when_titles_are_close(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi="10.5555/correct",
            title_candidate="Attention Is All You Need",
        )
        paper_data = {"title": "Attention is All You Need"}

        result = self.service._is_doi_title_mismatch(canonical, paper_data)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
