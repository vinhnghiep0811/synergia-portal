"""Integration tests: docling extraction and structure building."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


class DoclingAndBuildStructureIntegrationTests(IntegrationEphemeralTestCase):
    def test_build_structure_creates_chunks(self) -> None:
        paper_id = self.workflow.upload_pdf("doc.pdf", b"%PDF-1.4\ndoc")
        parsed = self.workflow.parse_and_map(paper_id, "DOI: 10.8888/doc")

        created = self.workflow.build_structure(
            parsed["canonical_key"],
            "Abstract paragraph.\n\nMethod paragraph.\n\nResult paragraph.",
        )

        chunks = self.workflow.chunks_for(parsed["canonical_key"])
        self.assertEqual(created, 3)
        self.assertEqual(len(chunks), 3)

    def test_first_chunk_marked_as_abstract(self) -> None:
        paper_id = self.workflow.upload_pdf("doc.pdf", b"%PDF-1.4\ndoc")
        parsed = self.workflow.parse_and_map(paper_id, "DOI: 10.8888/doc")
        self.workflow.build_structure(parsed["canonical_key"], "Abstract block.\n\nBody block.")

        chunks = self.workflow.chunks_for(parsed["canonical_key"])
        self.assertEqual(chunks[0]["section_type"], "abstract")
        self.assertEqual(chunks[1]["section_type"], "body")

    def test_empty_markdown_creates_no_chunks(self) -> None:
        paper_id = self.workflow.upload_pdf("doc.pdf", b"%PDF-1.4\ndoc")
        parsed = self.workflow.parse_and_map(paper_id, "DOI: 10.7777/empty")
        created = self.workflow.build_structure(parsed["canonical_key"], " \n\n ")

        self.assertEqual(created, 0)
        self.assertEqual(len(self.workflow.chunks_for(parsed["canonical_key"])), 0)

    def test_structure_is_scoped_per_canonical(self) -> None:
        p1 = self.workflow.upload_pdf("a.pdf", b"%PDF-1.4\na")
        p2 = self.workflow.upload_pdf("b.pdf", b"%PDF-1.4\nb")
        c1 = self.workflow.parse_and_map(p1, "DOI: 10.1234/a")["canonical_key"]
        c2 = self.workflow.parse_and_map(p2, "DOI: 10.1234/b")["canonical_key"]

        self.workflow.build_structure(c1, "A1\n\nA2")
        self.workflow.build_structure(c2, "B1")

        self.assertEqual(len(self.workflow.chunks_for(c1)), 2)
        self.assertEqual(len(self.workflow.chunks_for(c2)), 1)
