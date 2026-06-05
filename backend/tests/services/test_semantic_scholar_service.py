import os
import sys
import types
import unittest
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from sqlalchemy.types import String, TypeDecorator


class Vector(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, dimensions=None) -> None:
        self.dimensions = dimensions
        super().__init__()


pgvector_module = types.ModuleType("pgvector")
pgvector_sqlalchemy_module = types.ModuleType("pgvector.sqlalchemy")
pgvector_sqlalchemy_module.Vector = Vector
sys.modules.setdefault("pgvector", pgvector_module)
sys.modules.setdefault("pgvector.sqlalchemy", pgvector_sqlalchemy_module)

from app.services.semantic_scholar_service import SemanticScholarService


class FakeQuery:
    def __init__(self, result=None) -> None:
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class FakeDb:
    def __init__(self, query_result=None) -> None:
        self.query_result = query_result
        self.added = []
        self.commits = 0
        self.refreshed = []

    def query(self, *args, **kwargs):
        return FakeQuery(self.query_result)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        self.refreshed.append(value)


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


class SemanticScholarCrossrefFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(SemanticScholarService)
        self.service.api_key = "test-key"
        self.service.db = FakeDb()

    def test_run_uses_crossref_fallback_when_semantic_scholar_is_unmatched(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi=None,
            title_candidate="Electric Field Effect in Atomically Thin Carbon Films",
            enrichment_status="pending",
        )
        calls = []

        self.service._get_by_doi = lambda doi: (None, False)
        self.service._search_by_title = lambda title: (None, False)
        self.service._try_crossref_fallback = lambda canonical: calls.append(canonical.id) or "enriched"
        self.service._mark_rate_limited = lambda canonical: None
        self.service._mark_unmatched = lambda canonical: self.fail("should not mark unmatched")

        result = self.service.run_for_canonical_document(canonical)

        self.assertEqual(result, "enriched")
        self.assertEqual(calls, ["canonical-1"])

    def test_apply_crossref_data_populates_primary_metadata_fields(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi=None,
            title_candidate="Parsed title",
            title=None,
            publication_year=None,
            venue=None,
            abstract=None,
            authors_json=None,
            ss_paper_id="old-ss-id",
            ss_match_confidence=0.5,
            metadata_source=None,
            enrichment_status="pending",
            match_status=None,
            crossref_match_status=None,
            crossref_match_confidence=None,
            crossref_metadata_json=None,
            crossref_verification_json=None,
        )
        crossref_metadata = {
            "source": "crossref",
            "doi": "10.1126/science.1102896",
            "title": "Electric Field Effect in Atomically Thin Carbon Films",
            "authors": ["K. S. Novoselov", "A. K. Geim"],
            "year": 2004,
            "venue": "Science",
            "abstract": "Graphitic films are described.",
        }
        verification = {
            "status": "verified",
            "confidence": 0.95,
            "crossref_metadata": crossref_metadata,
        }

        self.service._apply_crossref_data(
            canonical,
            crossref_metadata,
            "matched_by_crossref_title",
            verification,
        )

        self.assertEqual(canonical.metadata_source, "crossref")
        self.assertEqual(canonical.enrichment_status, "enriched")
        self.assertEqual(canonical.match_status, "matched_by_crossref_title")
        self.assertEqual(canonical.doi, "10.1126/science.1102896")
        self.assertEqual(canonical.title, "Electric Field Effect in Atomically Thin Carbon Films")
        self.assertEqual(canonical.publication_year, 2004)
        self.assertEqual(canonical.venue, "Science")
        self.assertEqual(canonical.abstract, "Graphitic films are described.")
        self.assertEqual(
            canonical.authors_json,
            [
                {"name": "K. S. Novoselov", "author_id": None},
                {"name": "A. K. Geim", "author_id": None},
            ],
        )
        self.assertIsNone(canonical.ss_paper_id)
        self.assertIsNone(canonical.ss_match_confidence)
        self.assertEqual(canonical.crossref_match_status, "verified")
        self.assertEqual(canonical.crossref_match_confidence, 0.95)
        self.assertEqual(canonical.crossref_metadata_json, crossref_metadata)


class SemanticScholarCrossrefVerificationReplacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(SemanticScholarService)
        self.service.db = FakeDb()

    def test_apply_crossref_verification_replaces_missing_fields(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi=None,
            title=None,
            publication_year=None,
            venue=None,
            abstract=None,
            authors_json=None,
            crossref_match_status=None,
            crossref_match_confidence=None,
            crossref_metadata_json=None,
            crossref_verification_json=None,
        )

        verification = {
            "status": "verified",
            "confidence": 0.95,
            "crossref_metadata": {
                "doi": "10.1126/science.1102896",
                "title": "Electric Field Effect in Atomically Thin Carbon Films",
                "year": 2004,
                "venue": "Science",
                "abstract": "Graphitic films are described.",
                "authors": ["K. S. Novoselov", "A. K. Geim"],
            },
            "fields": {
                "doi": {
                    "status": "missing",
                    "primary": None,
                    "crossref": "10.1126/science.1102896",
                },
                "title": {
                    "status": "missing",
                    "primary": None,
                    "crossref": "Electric Field Effect in Atomically Thin Carbon Films",
                },
                "year": {
                    "status": "missing",
                    "primary": None,
                    "crossref": 2004,
                },
                "venue": {
                    "status": "missing",
                    "primary": None,
                    "crossref": "Science",
                },
                "abstract": {
                    "status": "missing",
                    "primary": None,
                    "crossref": "Graphitic films are described.",
                },
                "authors": {
                    "status": "missing",
                    "primary": [],
                    "crossref": ["K. S. Novoselov", "A. K. Geim"],
                },
            }
        }

        self.service._apply_crossref_verification(canonical, verification)

        self.assertEqual(canonical.doi, "10.1126/science.1102896")
        self.assertEqual(canonical.title, "Electric Field Effect in Atomically Thin Carbon Films")
        self.assertEqual(canonical.publication_year, 2004)
        self.assertEqual(canonical.venue, "Science")
        self.assertEqual(canonical.abstract, "Graphitic films are described.")
        self.assertEqual(
            canonical.authors_json,
            [
                {"name": "K. S. Novoselov", "author_id": None},
                {"name": "A. K. Geim", "author_id": None},
            ]
        )
    def test_run_for_canonical_document_heals_missing_fields_if_already_enriched(self) -> None:
        canonical = SimpleNamespace(
            id="canonical-1",
            doi=None,
            title=None,
            publication_year=None,
            venue=None,
            abstract=None,
            authors_json=None,
            crossref_match_status=None,
            crossref_match_confidence=None,
            crossref_metadata_json=None,
            crossref_verification_json={
                "status": "verified",
                "confidence": 0.95,
                "fields": {
                    "venue": {
                        "status": "missing",
                        "primary": None,
                        "crossref": "Science",
                    }
                }
            },
            enrichment_status="enriched",
        )
        self.service.api_key = "test-key"

        result = self.service.run_for_canonical_document(canonical)

        self.assertEqual(result, "skipped_already_enriched")
        self.assertEqual(canonical.venue, "Science")


if __name__ == "__main__":
    unittest.main()
