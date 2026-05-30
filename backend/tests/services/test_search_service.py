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
            query_coverage=self.service._query_coverage_score(query, intro_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, intro_chunk),
            phrase_score=self.service._phrase_match_score(query, intro_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, intro_chunk),
        )
        technique_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.78,
            section_boost=self.service._section_boost(technique_chunk.section_type),
            section_penalty=self.service._section_penalty(technique_chunk.section),
            query_boost=self.service._query_aware_boost(query, technique_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, technique_chunk),
            query_coverage=self.service._query_coverage_score(query, technique_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, technique_chunk),
            phrase_score=self.service._phrase_match_score(query, technique_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, technique_chunk),
        )

        self.assertGreater(technique_score, intro_score)
        self.assertLess(technique_score, 1.0)
        self.assertLess(intro_score, 1.0)

    def test_technical_relevance_requires_query_context_not_only_phrase_match(self) -> None:
        query = "Optimization techniques for sequence-to-sequence translation systems"
        unrelated_chunk = SimpleNamespace(
            section="Training",
            section_full_path="Training",
            section_type="other",
            content=(
                "We tried several optimization techniques such as Adam and "
                "RMSProp for image classification."
            ),
        )
        contextual_chunk = SimpleNamespace(
            section="Optimization",
            section_full_path="Optimization",
            section_type="other",
            content=(
                "For neural machine translation, the encoder decoder model uses "
                "Adam optimization and a learning rate schedule during training."
            ),
        )

        unrelated_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.86,
            section_boost=self.service._section_boost(unrelated_chunk.section_type),
            section_penalty=self.service._section_penalty(unrelated_chunk.section),
            query_boost=self.service._query_aware_boost(query, unrelated_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, unrelated_chunk),
            query_coverage=self.service._query_coverage_score(query, unrelated_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, unrelated_chunk),
            phrase_score=self.service._phrase_match_score(query, unrelated_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, unrelated_chunk),
        )
        contextual_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.78,
            section_boost=self.service._section_boost(contextual_chunk.section_type),
            section_penalty=self.service._section_penalty(contextual_chunk.section),
            query_boost=self.service._query_aware_boost(query, contextual_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, contextual_chunk),
            query_coverage=self.service._query_coverage_score(query, contextual_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, contextual_chunk),
            phrase_score=self.service._phrase_match_score(query, contextual_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, contextual_chunk),
        )

        self.assertGreater(contextual_score, unrelated_score)

    def test_translation_query_penalizes_other_task_sections(self) -> None:
        query = "Optimization techniques for sequence-to-sequence translation systems"
        parsing_chunk = SimpleNamespace(
            section="English Constituency Parsing",
            section_full_path="English Constituency Parsing",
            section_type="other",
            content=(
                "We selected dropout, learning rates and beam size on the "
                "development set, using the English-to-German base translation model."
            ),
        )
        translation_chunk = SimpleNamespace(
            section="Optimizer",
            section_full_path="Optimizer",
            section_type="other",
            content=(
                "For English-to-German neural machine translation, the encoder "
                "decoder model uses Adam optimization and a learning rate schedule."
            ),
        )

        parsing_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.86,
            section_boost=self.service._section_boost(parsing_chunk.section_type),
            section_penalty=self.service._section_penalty(parsing_chunk.section),
            query_boost=self.service._query_aware_boost(query, parsing_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, parsing_chunk),
            query_coverage=self.service._query_coverage_score(query, parsing_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, parsing_chunk),
            phrase_score=self.service._phrase_match_score(query, parsing_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, parsing_chunk),
        )
        translation_score = self.service._combined_relevance_score(
            query_type="technical_method",
            similarity=0.80,
            section_boost=self.service._section_boost(translation_chunk.section_type),
            section_penalty=self.service._section_penalty(translation_chunk.section),
            query_boost=self.service._query_aware_boost(query, translation_chunk),
            lexical_boost=self.service._lexical_relevance_boost(query, translation_chunk),
            query_coverage=self.service._query_coverage_score(query, translation_chunk),
            aspect_coverage=self.service._technical_aspect_coverage(query, translation_chunk),
            phrase_score=self.service._phrase_match_score(query, translation_chunk),
            task_penalty=self.service._task_mismatch_penalty(query, translation_chunk),
        )

        self.assertLess(self.service._task_mismatch_penalty(query, parsing_chunk), 0)
        self.assertGreater(translation_score, parsing_score)

    def test_document_diversity_penalty_reorders_close_duplicate_docs(self) -> None:
        doc_a = "doc-a"
        doc_b = "doc-b"
        selected = [
            {
                "chunk": SimpleNamespace(canonical_document_id=doc_a),
                "relevance": 0.90,
            },
            {
                "chunk": SimpleNamespace(canonical_document_id=doc_a),
                "relevance": 0.84,
            },
            {
                "chunk": SimpleNamespace(canonical_document_id=doc_b),
                "relevance": 0.82,
            },
        ]

        adjusted = self.service._apply_document_diversity_penalty(
            selected=selected,
            query_type="technical_method",
        )
        adjusted.sort(key=lambda item: item["relevance"], reverse=True)

        self.assertEqual(adjusted[0]["chunk"].canonical_document_id, doc_a)
        self.assertEqual(adjusted[1]["chunk"].canonical_document_id, doc_b)

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
