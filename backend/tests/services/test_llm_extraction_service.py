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


class LLMExtractionServiceLimitationsTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(LLMExtractionService)

    def test_normalize_limitations_drops_attention_intro_prior_work_dump(self):
        limitations = self.service._normalize_limitations_field(
            [
                {
                    "value": (
                        "## 1 Introduction Recurrent neural networks, long short-term memory "
                        "and gated recurrent neural networks in particular, have been firmly "
                        "established as state of the art approaches in sequence modeling"
                    ),
                    "evidence": [
                        {
                            "snippet": (
                                "## 1 Introduction Recurrent neural networks, long short-term "
                                "memory and gated recurrent neural networks in particular"
                            ),
                            "page": 1,
                            "section": None,
                        }
                    ],
                }
            ]
        )

        self.assertEqual(limitations, [])

    def test_normalize_limitations_accepts_explicit_future_work(self):
        limitations = self.service._normalize_limitations_field(
            [
                {
                    "value": "Future work should extend the model beyond text and handle large inputs efficiently.",
                    "evidence": [
                        {
                            "snippet": (
                                "We plan to extend the Transformer to problems involving input and "
                                "output modalities other than text"
                            ),
                            "page": 10,
                            "section": "Conclusion",
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(limitations), 1)
        self.assertIn("Future work", limitations[0]["value"])

    def test_coerce_from_input_text_does_not_turn_prior_work_weakness_into_limitation(self):
        result = self.service._coerce_from_input_text(
            "[ABSTRACT]\n"
            "We propose the Transformer, a model architecture based solely on attention mechanisms.\n\n"
            "[PAPER_TEXT]\n"
            "## 1 Introduction Recurrent neural networks, long short-term memory and gated "
            "recurrent neural networks in particular, have been firmly established as state "
            "of the art approaches in sequence modeling. Recurrent models typically factor "
            "computation along the symbol positions of the input and output sequences. This "
            "inherently sequential nature precludes parallelization within training examples."
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["limitations"], [])


class LLMExtractionServiceResearchFieldTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(LLMExtractionService)

    def test_coerce_prefers_current_paper_method_over_cited_prior_work(self):
        result = self.service._coerce_from_input_text(
            "[PAPER_TEXT]\n"
            "Vaswani et al. (2017) propose an architecture that avoids recurrence. "
            "While the proposed architecture achieves strong results, it requires many parameters. "
            "We propose Weighted Transformer, a Transformer with modified attention layers. "
            "Our model improves BLEU on the WMT 2014 English-to-German task."
        )

        self.assertIsNotNone(result)
        self.assertIn("Weighted Transformer", result["method"]["value"])
        self.assertNotIn("Vaswani", result["method"]["value"])

    def test_evaluation_extraction_keeps_wmt_and_bleu_but_drops_venues(self):
        text = (
            "We benchmark on the WMT 2014 English-to-German and English-to-French tasks. "
            "Results are reported using BLEU. Prior work appeared at EMNLP 2014 and NIPS 2014."
        )

        self.assertEqual(
            self.service._extract_datasets_from_text(text),
            ["WMT 2014 English-to-German", "WMT 2014 English-to-French"],
        )
        self.assertEqual(self.service._extract_metrics_from_text(text), ["BLEU"])


if __name__ == "__main__":
    unittest.main()
