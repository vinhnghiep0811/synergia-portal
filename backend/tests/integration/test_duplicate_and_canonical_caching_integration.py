"""Integration tests: duplicate handling and canonical cache."""

from tests.integration.fixtures import IntegrationEphemeralTestCase
from tests.integration.test_llm_extraction_integration import valid_payload


class DuplicateAndCanonicalCachingIntegrationTests(IntegrationEphemeralTestCase):
    def test_duplicate_links_second_paper_to_original(self) -> None:
        original = self.workflow.upload_pdf("o.pdf", b"%PDF-1.4\no")
        duplicate = self.workflow.upload_pdf("d.pdf", b"%PDF-1.4\nd")

        self.workflow.mark_duplicate(duplicate, original)
        dup_row = self.workflow.paper(duplicate)

        self.assertEqual(dup_row["duplicate_of"], original)
        self.assertEqual(dup_row["status"], "duplicate")

    def test_same_doi_reuses_canonical_cache_key(self) -> None:
        p1 = self.workflow.upload_pdf("1.pdf", b"%PDF-1.4\n1")
        p2 = self.workflow.upload_pdf("2.pdf", b"%PDF-1.4\n2")
        k1 = self.workflow.parse_and_map(p1, "DOI: 10.6666/shared")["canonical_key"]
        k2 = self.workflow.parse_and_map(p2, "DOI: 10.6666/shared")["canonical_key"]

        self.assertEqual(k1, k2)
        self.assertEqual(self.workflow.canonical_count(), 1)

    def test_cache_miss_returns_none(self) -> None:
        self.assertIsNone(self.workflow.get_cached_extraction("unknown"))

    def test_cached_extraction_is_shared_for_duplicate_flow(self) -> None:
        original = self.workflow.upload_pdf("orig.pdf", b"%PDF-1.4\norig")
        duplicate = self.workflow.upload_pdf("dup.pdf", b"%PDF-1.4\ndup")
        key = self.workflow.parse_and_map(original, "DOI: 10.7777/cache")["canonical_key"]
        self.workflow.parse_and_map(duplicate, "DOI: 10.7777/cache")
        self.workflow.mark_duplicate(duplicate, original)

        self.workflow.run_llm_extraction(key, valid_payload())
        cached = self.workflow.get_cached_extraction(key)

        self.assertIsNotNone(cached)
        self.assertIn("problem", cached)
