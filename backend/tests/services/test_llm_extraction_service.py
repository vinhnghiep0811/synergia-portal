import os
import sys
import types
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

pgvector_module = types.ModuleType("pgvector")
pgvector_sqlalchemy_module = types.ModuleType("pgvector.sqlalchemy")

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


pgvector_sqlalchemy_module.Vector = Vector
pgvector_module.sqlalchemy = pgvector_sqlalchemy_module
sys.modules.setdefault("pgvector", pgvector_module)
sys.modules.setdefault("pgvector.sqlalchemy", pgvector_sqlalchemy_module)

from app.services.llm_extraction_service import LLMExtractionService


class LLMExtractionServicePageMatchingTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(LLMExtractionService)

    def test_normalize_evidence_accepts_string_page_numbers(self):
        evidence = self.service._normalize_evidence(
            [
                {
                    "snippet": "The system evaluates metadata extraction quality.",
                    "page": "Page 12",
                    "section": "Evaluation",
                }
            ]
        )

        self.assertEqual(evidence[0]["page"], 12)

    def test_match_snippet_to_page_ignores_spacing_and_punctuation_differences(self):
        pages = [
            {"page": 1, "text": "Introductory material."},
            {
                "page": "2",
                "text": "We evaluate on the COCO dataset using\nBLEU score and human ratings.",
            },
        ]

        page = self.service._match_snippet_to_page(
            "We evaluate on the COCO dataset using BLEU score",
            pages,
        )

        self.assertEqual(page, 2)

    def test_match_snippet_to_page_uses_fuzzy_token_coverage(self):
        pages = [
            {"page": 1, "text": "Background and related work."},
            {
                "page": 3,
                "text": (
                    "This paper presents a robust architecture for noisy "
                    "documents and evaluates it across several benchmarks."
                ),
            },
        ]

        page = self.service._match_snippet_to_page(
            "presents a robust architecture for noisy document extraction and evaluates it",
            pages,
        )

        self.assertEqual(page, 3)


if __name__ == "__main__":
    unittest.main()
