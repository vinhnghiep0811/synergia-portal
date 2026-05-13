import os
import sys
import types
import unittest
from types import SimpleNamespace
from uuid import uuid4

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

from app.services.search_service import SearchService


def make_service() -> SearchService:
    return object.__new__(SearchService)


def make_chunk(
    *,
    section_type: str | None,
    section: str | None,
    section_full_path: str | None,
    embedding: list[float],
    canonical_document_id=None,
    chunk_id=None,
):
    return SimpleNamespace(
        id=chunk_id or uuid4(),
        canonical_document_id=canonical_document_id or uuid4(),
        section_type=section_type,
        section=section,
        section_full_path=section_full_path,
        embedding=embedding,
    )


class SearchHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def test_section_boost_returns_weight_for_known_section_type(self) -> None:
        self.assertEqual(self.service._section_boost("method"), 0.08)
        self.assertEqual(self.service._section_boost("unknown-section"), 0.0)
        self.assertEqual(self.service._section_boost(None), 0.0)

    def test_section_boost_supports_case_and_penalty_section_types(self) -> None:
        self.assertEqual(self.service._section_boost("REFERENCES"), -0.10)
        self.assertEqual(self.service._section_boost("related_work"), -0.01)
        self.assertEqual(self.service._section_boost("appendix"), -0.10)

    def test_section_penalty_applies_for_soft_excluded_keywords(self) -> None:
        self.assertEqual(self.service._section_penalty("Ablation qualitative result"), -0.04)
        self.assertEqual(self.service._section_penalty("Main results"), 0.0)

    def test_section_penalty_handles_case_study_and_none(self) -> None:
        self.assertEqual(self.service._section_penalty("Detailed Case Study"), -0.04)
        self.assertEqual(self.service._section_penalty(None), 0.0)

    def test_detect_query_type_variants_and_precedence(self) -> None:
        self.assertEqual(self.service._detect_query_type("How does A versus B work?"), "comparison")
        self.assertEqual(self.service._detect_query_type("Explain this workflow pipeline"), "process")
        self.assertEqual(self.service._detect_query_type("Find relevant passages"), "general")

    def test_query_aware_boost_process_query_boosts_method_section(self) -> None:
        chunk = make_chunk(
            section_type="method",
            section="Approach",
            section_full_path="Method > Approach",
            embedding=[1.0, 0.0],
        )

        boost = self.service._query_aware_boost("How does this workflow work?", chunk)

        self.assertEqual(boost, 0.10)

    def test_query_aware_boost_adds_keyword_pair_boost(self) -> None:
        chunk = make_chunk(
            section_type="other",
            section="Planning",
            section_full_path="Architecture > Planning",
            embedding=[1.0, 0.0],
        )

        boost = self.service._query_aware_boost("need a plan", chunk)

        self.assertEqual(boost, 0.06)

    def test_query_aware_boost_supports_more_query_types(self) -> None:
        results_chunk = make_chunk(
            section_type="results",
            section="Benchmarks",
            section_full_path="Results > Benchmarks",
            embedding=[1.0, 0.0],
        )
        discussion_chunk = make_chunk(
            section_type="discussion",
            section="Risks",
            section_full_path="Discussion > Risks",
            embedding=[1.0, 0.0],
        )
        intro_chunk = make_chunk(
            section_type="introduction",
            section="Overview",
            section_full_path="Introduction > Overview",
            embedding=[1.0, 0.0],
        )
        abstract_chunk = make_chunk(
            section_type="abstract",
            section="Summary",
            section_full_path="Abstract > Summary",
            embedding=[1.0, 0.0],
        )

        self.assertEqual(
            self.service._query_aware_boost("show benchmark performance", results_chunk),
            0.08,
        )
        self.assertEqual(
            self.service._query_aware_boost("what are the risks?", discussion_chunk),
            0.14,
        )
        self.assertEqual(
            self.service._query_aware_boost("how does this pipeline work?", intro_chunk),
            -0.03,
        )
        self.assertEqual(
            self.service._query_aware_boost("give me a summary", abstract_chunk),
            0.06,
        )

    def test_query_aware_boost_accumulates_multiple_keyword_pair_matches(self) -> None:
        chunk = make_chunk(
            section_type="method",
            section="Planning",
            section_full_path="Architecture > Planning > Memory Execution",
            embedding=[1.0, 0.0],
        )

        boost = self.service._query_aware_boost("how to plan and execute with memory", chunk)

        self.assertAlmostEqual(boost, 0.28)

    def test_is_hard_excluded_section_by_type_or_keyword(self) -> None:
        excluded_by_type = make_chunk(
            section_type="references",
            section="References",
            section_full_path="Back Matter > References",
            embedding=[1.0, 0.0],
        )
        excluded_by_keyword = make_chunk(
            section_type="other",
            section="Appendix A",
            section_full_path="Supplement > Appendix",
            embedding=[1.0, 0.0],
        )
        allowed = make_chunk(
            section_type="method",
            section="Method",
            section_full_path="Main > Method",
            embedding=[1.0, 0.0],
        )

        self.assertTrue(self.service._is_hard_excluded_section(excluded_by_type))
        self.assertTrue(self.service._is_hard_excluded_section(excluded_by_keyword))
        self.assertFalse(self.service._is_hard_excluded_section(allowed))

    def test_mmr_select_filters_near_duplicate_embeddings(self) -> None:
        doc_1 = uuid4()
        doc_2 = uuid4()
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
                canonical_document_id=doc_1,
            ),
            "relevance": 1.0,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Details",
                embedding=[0.99, 0.01],
                canonical_document_id=doc_1,
            ),
            "relevance": 0.9,
            "embedding": [0.99, 0.01],
        }
        candidate_c = {
            "chunk": make_chunk(
                section_type="results",
                section="Results",
                section_full_path="Results > Main",
                embedding=[0.0, 1.0],
                canonical_document_id=doc_2,
            ),
            "relevance": 0.8,
            "embedding": [0.0, 1.0],
        }

        selected = self.service._mmr_select(
            candidates=[candidate_a, candidate_b, candidate_c],
            top_k=2,
            duplicate_threshold=0.88,
        )

        selected_ids = [item["chunk"].id for item in selected]
        self.assertIn(candidate_a["chunk"].id, selected_ids)
        self.assertIn(candidate_c["chunk"].id, selected_ids)
        self.assertNotIn(candidate_b["chunk"].id, selected_ids)

    def test_mmr_select_returns_empty_when_candidates_are_empty(self) -> None:
        self.assertEqual(self.service._mmr_select(candidates=[], top_k=3), [])

    def test_mmr_select_keeps_first_item_when_top_k_is_zero(self) -> None:
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
            ),
            "relevance": 0.9,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="results",
                section="Results",
                section_full_path="Results > Main",
                embedding=[0.0, 1.0],
            ),
            "relevance": 0.8,
            "embedding": [0.0, 1.0],
        }

        selected = self.service._mmr_select(candidates=[candidate_a, candidate_b], top_k=0)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["chunk"].id, candidate_a["chunk"].id)

    def test_mmr_select_uses_input_order_when_scores_tie(self) -> None:
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
            ),
            "relevance": 1.0,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="results",
                section="Results",
                section_full_path="Results > B",
                embedding=[0.0, 1.0],
            ),
            "relevance": 0.7,
            "embedding": [0.0, 1.0],
        }
        candidate_c = {
            "chunk": make_chunk(
                section_type="discussion",
                section="Discussion",
                section_full_path="Discussion > C",
                embedding=[0.0, -1.0],
            ),
            "relevance": 0.7,
            "embedding": [0.0, -1.0],
        }

        selected = self.service._mmr_select(
            candidates=[candidate_a, candidate_b, candidate_c],
            top_k=2,
            duplicate_threshold=0.99,
        )

        self.assertEqual(selected[1]["chunk"].id, candidate_b["chunk"].id)

    def test_mmr_select_falls_back_to_relevance_when_all_remaining_are_duplicates(self) -> None:
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
            ),
            "relevance": 1.0,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Details",
                embedding=[1.0, 0.0],
            ),
            "relevance": 0.9,
            "embedding": [1.0, 0.0],
        }
        candidate_c = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Extra",
                embedding=[1.0, 0.0],
            ),
            "relevance": 0.8,
            "embedding": [1.0, 0.0],
        }

        selected = self.service._mmr_select(
            candidates=[candidate_a, candidate_b, candidate_c],
            top_k=2,
            duplicate_threshold=0.88,
        )

        self.assertEqual(selected[1]["chunk"].id, candidate_b["chunk"].id)

    def test_mmr_select_penalizes_same_section_root(self) -> None:
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
            ),
            "relevance": 0.95,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="method",
                section="Method details",
                section_full_path="Method > Details",
                embedding=[0.0, 1.0],
            ),
            "relevance": 0.90,
            "embedding": [0.0, 1.0],
        }
        candidate_c = {
            "chunk": make_chunk(
                section_type="results",
                section="Results",
                section_full_path="Results > Main",
                embedding=[0.0, 1.0],
            ),
            "relevance": 0.86,
            "embedding": [0.0, 1.0],
        }

        selected = self.service._mmr_select(
            candidates=[candidate_a, candidate_b, candidate_c],
            top_k=2,
            duplicate_threshold=0.99,
        )

        self.assertEqual(selected[1]["chunk"].id, candidate_c["chunk"].id)

    def test_mmr_select_comparison_mode_prefers_new_document(self) -> None:
        doc_1 = uuid4()
        doc_2 = uuid4()
        candidate_a = {
            "chunk": make_chunk(
                section_type="method",
                section="Method",
                section_full_path="Method > Main",
                embedding=[1.0, 0.0],
                canonical_document_id=doc_1,
            ),
            "relevance": 0.9,
            "embedding": [1.0, 0.0],
        }
        candidate_b = {
            "chunk": make_chunk(
                section_type="results",
                section="Results",
                section_full_path="Results > Main",
                embedding=[0.0, 1.0],
                canonical_document_id=doc_1,
            ),
            "relevance": 0.72,
            "embedding": [0.0, 1.0],
        }
        candidate_c = {
            "chunk": make_chunk(
                section_type="discussion",
                section="Discussion",
                section_full_path="Discussion > Main",
                embedding=[0.0, 1.0],
                canonical_document_id=doc_2,
            ),
            "relevance": 0.68,
            "embedding": [0.0, 1.0],
        }

        selected = self.service._mmr_select(
            candidates=[candidate_a, candidate_b, candidate_c],
            top_k=2,
            query_type="comparison",
        )

        self.assertEqual(selected[0]["chunk"].id, candidate_a["chunk"].id)
        self.assertEqual(selected[1]["chunk"].id, candidate_c["chunk"].id)

    def test_ensure_multi_document_injects_missing_document(self) -> None:
        doc_1 = uuid4()
        doc_2 = uuid4()
        selected = [
            {
                "chunk": make_chunk(
                    section_type="method",
                    section="Method",
                    section_full_path="Method > Main",
                    embedding=[1.0, 0.0],
                    canonical_document_id=doc_1,
                ),
                "relevance": 0.95,
                "embedding": [1.0, 0.0],
            }
        ]
        candidates = selected + [
            {
                "chunk": make_chunk(
                    section_type="results",
                    section="Results",
                    section_full_path="Results > Main",
                    embedding=[0.0, 1.0],
                    canonical_document_id=doc_2,
                ),
                "relevance": 0.90,
                "embedding": [0.0, 1.0],
            }
        ]

        final = self.service._ensure_multi_document(selected=selected, candidates=candidates, top_k=2)
        final_doc_ids = {item["chunk"].canonical_document_id for item in final}

        self.assertEqual(len(final), 2)
        self.assertIn(doc_1, final_doc_ids)
        self.assertIn(doc_2, final_doc_ids)

    def test_keyword_score_priority_prefers_title_then_doi(self) -> None:
        in_title = self.service._keyword_score(
            q_lower="graph",
            title="Graph Retrieval",
            filename="paper.pdf",
            doi="10.1000/graph",
            content="content",
        )
        in_doi = self.service._keyword_score(
            q_lower="10.1000/graph",
            title="Retrieval",
            filename="paper.pdf",
            doi="10.1000/graph",
            content="content",
        )

        self.assertEqual(in_title, 1.0)
        self.assertEqual(in_doi, 0.95)

    def test_keyword_score_handles_filename_content_and_default(self) -> None:
        in_filename = self.service._keyword_score(
            q_lower="paper",
            title="Semantic retrieval",
            filename="best-paper.pdf",
            doi=None,
            content="content",
        )
        in_content = self.service._keyword_score(
            q_lower="needle",
            title="Semantic retrieval",
            filename="best-paper.pdf",
            doi=None,
            content="contains a needle in this content",
        )
        no_match = self.service._keyword_score(
            q_lower="absent",
            title="Semantic retrieval",
            filename="best-paper.pdf",
            doi=None,
            content="contains a needle in this content",
        )

        self.assertEqual(in_filename, 0.9)
        self.assertEqual(in_content, 0.75)
        self.assertEqual(no_match, 0.5)

    def test_chunk_keyword_score_handles_empty_content(self) -> None:
        score = self.service._chunk_keyword_score(
            query="graph retrieval",
            title="Graph paper",
            section="Method",
            content=None,
        )

        self.assertEqual(score, 0.0)

    def test_chunk_keyword_score_caps_and_partial_term_coverage(self) -> None:
        capped = self.service._chunk_keyword_score(
            query="graph retrieval",
            title="Graph Retrieval",
            section="Graph Retrieval",
            content=" ".join(["graph retrieval"] * 20),
        )
        partial = self.service._chunk_keyword_score(
            query="graph retrieval",
            title="Graph paper",
            section="Method",
            content="graph only appears once",
        )
        empty_query = self.service._chunk_keyword_score(
            query="   ",
            title="Graph paper",
            section="Method",
            content="graph retrieval text",
        )

        self.assertEqual(capped, 1.0)
        self.assertEqual(partial, 0.5)
        self.assertEqual(empty_query, 0.0)

    def test_cosine_similarity_handles_edge_cases(self) -> None:
        self.assertEqual(self.service._cosine_similarity(None, [1.0, 0.0]), 0.0)
        self.assertEqual(self.service._cosine_similarity([], []), 0.0)
        self.assertEqual(self.service._cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)
        self.assertAlmostEqual(self.service._cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertAlmostEqual(self.service._cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


if __name__ == "__main__":
    unittest.main()
