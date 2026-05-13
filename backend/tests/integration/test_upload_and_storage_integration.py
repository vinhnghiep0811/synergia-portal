"""Integration tests: upload and storage flow."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


class UploadAndStorageIntegrationTests(IntegrationEphemeralTestCase):
    def test_upload_pdf_persists_record_and_storage(self) -> None:
        paper_id = self.workflow.upload_pdf("paper.pdf", b"%PDF-1.4\ncontent")
        paper = self.workflow.paper(paper_id)

        self.assertEqual(paper["status"], "uploaded")
        self.assertTrue(paper["storage_path"].startswith("s3://papers/"))
        self.assertEqual(len(self.workflow.storage.list_paths()), 1)

    def test_upload_rejects_invalid_extension(self) -> None:
        with self.assertRaises(ValueError):
            self.workflow.upload_pdf("paper.txt", b"%PDF-1.4\ncontent")

    def test_upload_rejects_corrupted_pdf(self) -> None:
        with self.assertRaises(ValueError):
            self.workflow.upload_pdf("paper.pdf", b"not-a-pdf")

    def test_upload_rejects_oversize_file(self) -> None:
        with self.assertRaises(ValueError):
            self.workflow.upload_pdf("paper.pdf", b"%PDF" + (b"x" * (21 * 1024 * 1024)))

    def test_upload_rejects_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            self.workflow.upload_pdf("paper.pdf", b"")

    def test_storage_download_returns_content(self) -> None:
        content = b"%PDF-1.4\npayload"
        paper_id = self.workflow.upload_pdf("paper.pdf", content)
        paper = self.workflow.paper(paper_id)

        downloaded = self.workflow.storage.download(paper["storage_path"])

        self.assertEqual(downloaded, content)

    def test_storage_download_missing_path_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.workflow.storage.download("s3://papers/missing.pdf")

    def test_paper_lookup_raises_for_missing_id(self) -> None:
        with self.assertRaises(KeyError):
            self.workflow.paper("missing-paper-id")
