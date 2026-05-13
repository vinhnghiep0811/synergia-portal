"""Integration tests: parse and canonical mapping."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


class ParseAndCanonicalMappingIntegrationTests(IntegrationEphemeralTestCase):
    def test_parse_uses_doi_as_canonical_key(self) -> None:
        paper_id = self.workflow.upload_pdf("a.pdf", b"%PDF-1.4\nA")
        result = self.workflow.parse_and_map(
            paper_id,
            "This paper includes DOI 10.1000/xyz123 in text.",
        )

        self.assertEqual(result["canonical_type"], "DOI")
        self.assertEqual(result["canonical_key"], "10.1000/xyz123")

    def test_parse_falls_back_to_fingerprint_without_doi(self) -> None:
        paper_id = self.workflow.upload_pdf("b.pdf", b"%PDF-1.4\nB")
        result = self.workflow.parse_and_map(paper_id, "No DOI exists in this document.")

        self.assertEqual(result["canonical_type"], "FINGERPRINT")
        self.assertTrue(len(result["canonical_key"]) > 10)

    def test_same_doi_reuses_single_canonical(self) -> None:
        p1 = self.workflow.upload_pdf("p1.pdf", b"%PDF-1.4\nP1")
        p2 = self.workflow.upload_pdf("p2.pdf", b"%PDF-1.4\nP2")

        r1 = self.workflow.parse_and_map(p1, "DOI: 10.5555/shared")
        r2 = self.workflow.parse_and_map(p2, "Random text DOI 10.5555/shared.")

        self.assertEqual(r1["canonical_key"], r2["canonical_key"])
        self.assertEqual(self.workflow.canonical_count(), 1)

    def test_duplicate_mapping_marks_paper(self) -> None:
        original = self.workflow.upload_pdf("original.pdf", b"%PDF-1.4\nORIGINAL")
        duplicate = self.workflow.upload_pdf("dup.pdf", b"%PDF-1.4\nDUP")
        self.workflow.mark_duplicate(duplicate, original)

        paper = self.workflow.paper(duplicate)
        self.assertEqual(paper["status"], "duplicate")
        self.assertEqual(paper["duplicate_of"], original)
