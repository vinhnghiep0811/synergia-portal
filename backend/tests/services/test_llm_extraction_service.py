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

    def test_fill_missing_pages_uses_docling_blocks_for_page_and_section(self):
        pages = [
            {
                "page": 1,
                "text": "Introductory material.",
                "sections": ["Introduction"],
                "blocks": [
                    {
                        "page": 1,
                        "section": "Introduction",
                        "text": "Introductory material.",
                    }
                ],
            },
            {
                "page": 7,
                "text": "We plan to investigate local restricted attention mechanisms further.",
                "sections": ["Conclusion"],
                "blocks": [
                    {
                        "page": 7,
                        "section": "Conclusion",
                        "text": "We plan to investigate local restricted attention mechanisms further.",
                    }
                ],
            },
        ]
        field = {
            "value": "The authors plan to investigate restricted attention further.",
            "evidence": [
                {
                    "snippet": "We plan to investigate local restricted attention mechanisms further.",
                    "page": None,
                    "section": None,
                }
            ],
        }

        filled = self.service._fill_missing_pages(field, pages)

        self.assertEqual(filled["evidence"][0]["page"], 7)
        self.assertEqual(filled["evidence"][0]["section"], "Conclusion")


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

    def test_normalize_limitations_accepts_metric_shortcoming_caveat(self):
        limitations = self.service._normalize_limitations_field(
            [
                {
                    "value": (
                        "ROUGE scores have shortcomings and should not be the only metric "
                        "to optimize for long-sequence summarization models."
                    ),
                    "evidence": [
                        {
                            "snippet": (
                                "ROUGE scores have their short- comings and should not be "
                                "the only metric to optimize"
                            ),
                            "page": 9,
                            "section": "Conclusion",
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(limitations), 1)
        self.assertIn("ROUGE", limitations[0]["value"])

    def test_normalize_limitations_accepts_further_research_direction(self):
        limitations = self.service._normalize_limitations_field(
            [
                {
                    "value": (
                        "Applying the model to other long sequence-to-sequence tasks is "
                        "an interesting direction for further research."
                    ),
                    "evidence": [
                        {
                            "snippet": (
                                "could be applied to other sequence-to-sequence tasks with long inputs "
                                "and outputs, which is an interesting direction for further research"
                            ),
                            "page": 9,
                            "section": "Conclusion",
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(limitations), 1)
        self.assertIn("further research", limitations[0]["value"])

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

    def test_coerce_from_input_text_drops_autoregressive_prior_work_limitation(self):
        result = self.service._coerce_from_input_text(
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "However, because of their auto-regressive property of requiring previous hidden "
            "states to be computed before the current time step, they cannot benefit from "
            "parallelization."
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["limitations"], [])

    def test_normalize_result_drops_limitation_from_introduction_context(self):
        input_text = (
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "However, because of their auto-regressive property of requiring previous hidden "
            "states to be computed before the current time step, they cannot benefit from "
            "parallelization.\n"
            "2 Method\n"
            "We introduce Weighted Transformer with multiple self-attention branches.\n"
            "6 Conclusion\n"
            "We introduced Weighted Transformer for machine translation."
        )
        raw = {
            "problem": {"value": None, "evidence": []},
            "method": {
                "value": "The paper introduces Weighted Transformer with multiple self-attention branches.",
                "evidence": [
                    {
                        "snippet": "We introduce Weighted Transformer with multiple self-attention branches.",
                        "page": None,
                        "section": None,
                    }
                ],
            },
            "contributions": [],
            "limitations": [
                {
                    "value": "Autoregressive models cannot benefit from parallelization.",
                    "evidence": [
                        {
                            "snippet": (
                                "because of their auto-regressive property of requiring previous hidden "
                                "states to be computed before the current time step, they cannot benefit "
                                "from parallelization"
                            ),
                            "page": None,
                            "section": "Conclusion",
                        }
                    ],
                }
            ],
            "evaluation_setup": {
                "value": {"datasets": [], "metrics": [], "benchmarks": []},
                "evidence": [],
            },
        }

        result = self.service._normalize_result(raw, pages=[], input_text=input_text)

        self.assertEqual(result["limitations"], [])

    def test_normalize_result_keeps_future_work_from_conclusion_context(self):
        input_text = (
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "We introduce a model for machine translation.\n"
            "6 Conclusion\n"
            "We plan to extend the Transformer to problems involving input and output "
            "modalities other than text."
        )
        raw = {
            "problem": {"value": None, "evidence": []},
            "method": {"value": None, "evidence": []},
            "contributions": [],
            "limitations": [
                {
                    "value": "The authors plan to extend the model beyond text modalities.",
                    "evidence": [
                        {
                            "snippet": (
                                "We plan to extend the Transformer to problems involving input and "
                                "output modalities other than text"
                            ),
                            "page": None,
                            "section": None,
                        }
                    ],
                }
            ],
            "evaluation_setup": {
                "value": {"datasets": [], "metrics": [], "benchmarks": []},
                "evidence": [],
            },
        }

        result = self.service._normalize_result(raw, pages=[], input_text=input_text)

        self.assertEqual(len(result["limitations"]), 1)
        self.assertIn("extend the model", result["limitations"][0]["value"])

    def test_coerce_from_input_text_extracts_conclusion_metric_caveat(self):
        result = self.service._coerce_from_input_text(
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "We introduce a summarization model for long documents.\n"
            "7 Conclusion\n"
            "We saw that despite their common use for evaluation, ROUGE scores have their "
            "short-\ncomings and should not be the only metric to opti-\nmize on summarization "
            "model for long sequences."
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result["limitations"]), 1)
        self.assertIn("ROUGE", result["limitations"][0]["value"])

    def test_normalize_result_drops_metric_caveat_from_introduction_context(self):
        input_text = (
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "ROUGE scores have shortcomings and should not be the only metric to optimize "
            "summarization models.\n"
            "2 Method\n"
            "We introduce a new summarization model."
        )
        raw = {
            "problem": {"value": None, "evidence": []},
            "method": {"value": None, "evidence": []},
            "contributions": [],
            "limitations": [
                {
                    "value": (
                        "ROUGE scores have shortcomings and should not be the only metric "
                        "to optimize summarization models."
                    ),
                    "evidence": [
                        {
                            "snippet": (
                                "ROUGE scores have shortcomings and should not be the only "
                                "metric to optimize summarization models"
                            ),
                            "page": None,
                            "section": "Conclusion",
                        }
                    ],
                }
            ],
            "evaluation_setup": {
                "value": {"datasets": [], "metrics": [], "benchmarks": []},
                "evidence": [],
            },
        }

        result = self.service._normalize_result(raw, pages=[], input_text=input_text)

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

    def test_benchmark_extraction_uses_named_table_rows(self):
        text = (
            "Table 2: The Transformer achieves better BLEU scores than previous models.\n\n"
            "| Model | BLEU | Training Cost |\n"
            "|-------|------|---------------|\n"
            "| ByteNet [18] | 23.75 | |\n"
            "| Deep-Att + PosUnk [39] | 39.2 | 1.0e20 |\n"
            "| GNMT + RL [38] | 24.6 | 2.3e19 |\n"
            "| Transformer (big) | 28.4 | 2.3e19 |\n"
        )

        self.assertEqual(
            self.service._extract_benchmarks_from_text(text),
            ["ByteNet", "Deep-Att + PosUnk", "GNMT + RL"],
        )

    def test_evaluation_normalization_rejects_generic_benchmarks(self):
        raw = {
            "value": {
                "datasets": ["WMT'14 English-to-German"],
                "metrics": ["BLEU"],
                "benchmarks": [
                    "state-of-the-art baseline",
                    "SMT system",
                    "encoder-decoder baseline",
                    "ByteNet [18]",
                ],
            },
            "evidence": [
                {
                    "snippet": "Table 2 summarizes our results and compares our translation quality.",
                    "page": 8,
                    "section": "Results",
                }
            ],
        }

        normalized = self.service._normalize_evaluation_setup(raw, pages=[], source_text="")

        self.assertEqual(normalized["value"]["benchmarks"], ["ByteNet"])
        self.assertNotIn("state-of-the-art baseline", normalized["value"]["benchmarks"])


if __name__ == "__main__":
    unittest.main()
