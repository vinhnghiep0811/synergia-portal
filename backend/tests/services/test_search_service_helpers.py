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


if __name__ == "__main__":
    unittest.main()
