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

    def test_is_allowed_limitation_section_matches_new_headings(self):
        new_headings = [
            "Future Trends and Challenges",
            "future trends",
            "Challenges",
            "Open Problems",
            "Perspectives",
            "Future Directions",
            "Future Research",
            "threats",
            "threats to validity"
        ]
        for heading in new_headings:
            with self.subTest(heading=heading):
                self.assertTrue(self.service._is_allowed_limitation_section(heading))

    def test_normalize_result_keeps_limitation_from_future_trends_and_challenges_context(self):
        input_text = (
            "[PAPER_TEXT]\n"
            "1 Introduction\n"
            "We introduce a model for machine translation.\n"
            "9 Future Trends and Challenges\n"
            "However, battery degradation remains a key challenge for vehicle-to-grid integration."
        )
        raw = {
            "problem": {"value": None, "evidence": []},
            "method": {"value": None, "evidence": []},
            "contributions": [],
            "limitations": [
                {
                    "value": "Battery degradation is a challenge for vehicle-to-grid integration.",
                    "evidence": [
                        {
                            "snippet": "battery degradation remains a key challenge for vehicle-to-grid integration",
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
        self.assertIn("Battery degradation", result["limitations"][0]["value"])


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

    def test_repair_joined_text_does_not_split_metal_terms(self):
        repaired = self.service._repair_joined_extraction_text(
            "metal metallic all-metallic Metal. Aetal. reported the result."
        )

        self.assertIn("metal metallic all-metallic Metal.", repaired)
        self.assertIn("A et al. reported the result.", repaired)
        self.assertNotIn("m et al.", repaired)

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

    def test_normalize_contributions_keeps_training_and_transfer_claim(self):
        normalized = self.service._normalize_contributions_field(
            [
                {
                    "value": (
                        "The paper analyzes several language pairs and demonstrates "
                        "transfer of encoder knowledge to low-resource languages."
                    ),
                    "evidence": [
                        {
                            "snippet": (
                                "we train the Transformer system from English to seven languages "
                                "... we also test attention in a transfer learning scenario"
                            ),
                            "page": 1,
                            "section": "Abstract",
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(normalized), 1)
        self.assertIn("transfer of encoder knowledge", normalized[0]["value"])

    def test_normalize_contributions_keeps_relaxed_past_tense_verbs(self):
        normalized = self.service._normalize_contributions_field(
            [
                {
                    "value": "Realized an all-metallic transistor.",
                    "evidence": []
                },
                {
                    "value": "Observed pronounced oscillations in graphene.",
                    "evidence": []
                }
            ]
        )
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["value"], "Realized an all-metallic transistor.")
        self.assertEqual(normalized[1]["value"], "Observed pronounced oscillations in graphene.")

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

    def test_detect_paper_type_does_not_treat_experimental_system_as_system_paper(self):
        text = (
            "Studies of Shubnikov-de Haas oscillations confirmed that electronic transport "
            "in FLG was strictly 2D and served as an indicator of the quality and homogeneity "
            "of the experimental system."
        )

        self.assertNotEqual(self.service._detect_paper_type(text), "system")

    def test_evaluation_normalization_keeps_domain_metrics_and_material_benchmarks(self):
        raw = {
            "value": {
                "datasets": [],
                "metrics": [
                    "carrier mobility",
                    "carrier concentration",
                    "Shubnikov-de Haas oscillation amplitude",
                    "resistivity",
                    "Hall coefficient",
                ],
                "benchmarks": ["multilayer graphene", "bulk graphite"],
            },
            "evidence": [
                {
                    "snippet": (
                        "The linear dependence BF on Vg proves a constant 2D density "
                        "of states and yields the double-valley degeneracy."
                    ),
                    "page": 3,
                    "section": "Results",
                }
            ],
        }

        normalized = self.service._normalize_evaluation_setup(raw, pages=[], source_text="")

        self.assertEqual(
            normalized["value"]["metrics"],
            [
                "carrier mobility",
                "carrier concentration",
                "Shubnikov-de Haas oscillation amplitude",
                "resistivity",
                "Hall coefficient",
            ],
        )
        self.assertEqual(normalized["value"]["benchmarks"], ["multilayer graphene", "bulk graphite"])

    def test_semantic_correction_preserves_non_system_evaluation_setup(self):
        raw = {
            "evaluation_setup": {
                "value": {
                    "datasets": [],
                    "metrics": ["carrier mobility", "Hall coefficient"],
                    "benchmarks": ["multilayer graphene", "bulk graphite"],
                },
                "evidence": [
                    {
                        "snippet": (
                            "Studies of Shubnikov-de Haas oscillations confirmed that "
                            "electronic transport in FLG was strictly 2D."
                        ),
                        "page": 3,
                        "section": "Results",
                    }
                ],
            }
        }
        full_text = (
            "The films exhibit pronounced Shubnikov-de Haas oscillations. "
            "This serves as an indicator of the quality and homogeneity of the experimental system. "
            "These properties differ from multilayer graphene and bulk graphite."
        )

        corrected = self.service._apply_semantic_correction(raw, full_text)

        self.assertEqual(
            corrected["evaluation_setup"]["value"]["metrics"],
            ["carrier mobility", "Hall coefficient"],
        )
        self.assertEqual(
            corrected["evaluation_setup"]["value"]["benchmarks"],
            ["multilayer graphene", "bulk graphite"],
        )

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

    def test_survey_paper_skips_evaluation_enrichment(self):
        text = "This paper presents a review of existing recycling methods for batteries on GLUE and precision."
        normalized = self.service._normalize_evaluation_setup(
            {"value": {"datasets": [], "metrics": []}, "evidence": []},
            pages=[],
            source_text=text
        )
        self.assertEqual(normalized["value"]["datasets"], [])
        self.assertEqual(normalized["value"]["metrics"], [])

    def test_new_limitation_signals(self):
        self.assertTrue(self.service._has_limitation_signal("obstacles remain to be overcome"))
        self.assertTrue(self.service._has_limitation_signal("these methods are not yet efficient"))
        self.assertTrue(self.service._has_limitation_signal("there are major barriers to scalability"))
        self.assertTrue(self.service._has_limitation_signal("recycling may not always reduce greenhouse gas emissions"))
        self.assertTrue(self.service._has_limitation_signal("this might not in all cases result in improvements"))
        self.assertTrue(self.service._has_limitation_signal("it is not necessarily viable"))
        self.assertTrue(self.service._has_limitation_signal("it is difficult to scale to production size"))

    def test_noisy_extraction_sentence_filtering(self):
        # Email address
        self.assertTrue(self.service._is_noisy_extraction_sentence("Contact us at author@university.edu for details"))
        # Affiliation headers
        self.assertTrue(self.service._is_noisy_extraction_sentence("Jiang 1 Department of Physics, University of Manchester"))
        self.assertTrue(self.service._is_noisy_extraction_sentence("Institute for Microelectronics Technology, Chernogolovka, Russia"))
        # Figure/table references
        self.assertTrue(self.service._is_noisy_extraction_sentence("Figure 2 shows the calculated dependences"))
        self.assertTrue(self.service._is_noisy_extraction_sentence("table 1: comparison of models"))
        
        # Valid contribution sentence should NOT be noisy
        self.assertFalse(self.service._is_noisy_extraction_sentence("We propose a novel framework for deep learning."))

    def test_fallback_contribution_deduplication_and_prefix_repair(self):
        # Check prefix repair
        repaired = self.service._repair_joined_extraction_text("One-sentence summary: We report a naturally-occurring material.")
        self.assertEqual(repaired, "We report a naturally-occurring material.")

        # Check deduplication of near-duplicates in candidate picking
        sentences = [
            "We report the electric field effect in few-layer graphene (FLG).",
            "Here we report the electric field effect in few-layer graphene (FLG).",
            "We describe a metallic field-effect transistor."
        ]
        candidates = self.service._pick_contribution_sentences(sentences, max_items=3)
        # The first and second sentences are near-duplicates, so only one should be kept
        self.assertEqual(len(candidates), 2)
        self.assertIn("We report the electric field effect in few-layer graphene (FLG).", candidates)
        self.assertNotIn("Here we report the electric field effect in few-layer graphene (FLG).", candidates)
        self.assertIn("We describe a metallic field-effect transistor.", candidates)


    def test_direct_llm_vs_fallback_validation_rules(self):
        # Case 1: Contribution
        # A creative contribution statement from LLM without strict words like "we/our"
        item_contrib = {"value": "The first demonstration of stable monocrystalline graphitic films under ambient conditions."}
        # For direct LLM (is_fallback=False), this should be accepted
        self.assertTrue(self.service._is_valid_contribution_item(item_contrib, is_fallback=False))
        # For fallback (is_fallback=True), this should be rejected because it has no claim owner or matching verb pattern
        self.assertFalse(self.service._is_valid_contribution_item(item_contrib, is_fallback=True))

        # Case 2: Limitation
        # A creative limitation statement from LLM without strict signal words
        item_limit = {"value": "The model has high computational complexity during inference."}
        # For direct LLM (is_fallback=False), this should be accepted
        self.assertTrue(self.service._is_valid_limitation_item(item_limit, is_fallback=False))
        # For fallback (is_fallback=True), this should be rejected because it lacks limitation keywords
        self.assertFalse(self.service._is_valid_limitation_item(item_limit, is_fallback=True))


if __name__ == "__main__":
    unittest.main()
