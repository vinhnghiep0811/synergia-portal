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

    def test_technical_relevance_does_not_saturate_or_prefer_broad_intro(self) -> None:
        query = "Optimization techniques for sequence-to-sequence translation systems"
        intro_chunk = SimpleNamespace(
            section="Introduction",
            section_full_path="Introduction",
            section_type="introduction",
            content=(
                "Recurrent neural networks are state of the art approaches in "
                "sequence modeling and machine translation."
            ),
        )
        technique_chunk = SimpleNamespace(
            section="Training technique",
            section_full_path="Training technique",
            section_type="other",
            content=(
                "We tried several high order optimization techniques such as "
                "AdaDelta, RMSProp and Adam to speed up training compared to SGD."
            ),
        )

        intro_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.92,
            section_boost=self.service._section_boost(intro_chunk.section_type),
            section_penalty=self.service._section_penalty(intro_chunk.section),
            query_boost=self.service._query_aware_boost(query, intro_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, intro_chunk),
        )
        technique_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.78,
            section_boost=self.service._section_boost(technique_chunk.section_type),
            section_penalty=self.service._section_penalty(technique_chunk.section),
            query_boost=self.service._query_aware_boost(query, technique_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, technique_chunk),
        )

        self.assertGreater(technique_score, intro_score)
        self.assertLess(technique_score, 1.0)
        self.assertLess(intro_score, 1.0)

    def test_technical_query_lexical_terms_focus_on_evidence_terms(self) -> None:
        query = "Optimization techniques for sequence-to-sequence translation systems"

        terms = self.service._semantic_lexical_terms(query, "technical_method")
        expanded_tokens = self.service._expanded_search_tokens(query)

        self.assertIn("optimization", terms)
        self.assertIn("adam", terms)
        self.assertIn("beam search", terms)
        self.assertNotIn("attention", expanded_tokens)

    def test_page_number_match_accepts_common_page_keys(self) -> None:
        pages = [
            {
                "page_number": "3",
                "text": "This page describes optimization techniques such as Adam and RMSProp.",
            }
        ]

        page = self.service._match_snippet_to_page(
            "optimization techniques such as Adam and RMSProp",
            pages,
        )

        self.assertEqual(page, 3)


if __name__ == "__main__":
    unittest.main()
