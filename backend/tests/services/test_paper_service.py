import os
import sys
import types
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

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

queue_service_module = types.ModuleType("app.services.queue_service")
storage_service_module = types.ModuleType("app.services.storage_service")
activity_log_service_module = types.ModuleType("app.services.activity_log_service")


class QueueService:
    def enqueue_pdf_parse(self, paper_id: str):
        return paper_id


class StorageService:
    def upload_pdf_bytes(self, **kwargs):
        return "s3://papers/papers/test.pdf"


class ActivityLogService:
    def __init__(self, db) -> None:
        self.db = db

    def log_paper_uploaded(self, **kwargs):
        return kwargs

    def log_parse_queued(self, **kwargs):
        return kwargs

    def log_parse_queue_failed(self, **kwargs):
        return kwargs


queue_service_module.QueueService = QueueService
storage_service_module.StorageService = StorageService
activity_log_service_module.ActivityLogService = ActivityLogService
sys.modules.setdefault("app.services.queue_service", queue_service_module)
sys.modules.setdefault("app.services.storage_service", storage_service_module)
sys.modules.setdefault("app.services.activity_log_service", activity_log_service_module)

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.services.paper_service import PaperService


VALID_PDF_BYTES = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] >>
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""


def make_upload_file(
    filename: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class PaperServiceUploadValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.service = PaperService(self.db)
        self.service.repo = Mock()
        self.service.storage = Mock()
        self.service.storage.upload_pdf_bytes.return_value = "s3://papers/papers/test.pdf"
        self.service.queue_service = Mock()
        self.service.activity_service = Mock()

    async def test_upload_pdf_accepts_valid_pdf(self) -> None:
        file = make_upload_file("valid.pdf", VALID_PDF_BYTES)

        paper = await self.service.upload_pdf(file, uploader_id="tester@example.com")

        self.assertEqual(paper.original_filename, "valid.pdf")
        self.assertEqual(paper.mime_type, "application/pdf")
        self.assertEqual(paper.file_size_bytes, len(VALID_PDF_BYTES))
        self.assertEqual(paper.processing_status, "pending")
        self.assertEqual(paper.processing_stage, "queued")
        self.assertEqual(paper.publication_status, "draft")
        self.service.storage.upload_pdf_bytes.assert_called_once()
        self.service.repo.create.assert_called_once()
        self.service.queue_service.enqueue_pdf_parse.assert_called_once_with(str(paper.id))
        self.assertEqual(self.db.commit.call_count, 2)

    async def test_upload_pdf_rejects_wrong_file_extension(self) -> None:
        file = make_upload_file("notes.txt", b"plain text", content_type="text/plain")

        with self.assertRaises(HTTPException) as context:
            await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Only PDF files are allowed.")
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_accepts_uppercase_extension_and_defaults_mime_type(self) -> None:
        file = UploadFile(
            file=BytesIO(VALID_PDF_BYTES),
            filename="UPPER.PDF",
            headers=Headers({}),
        )

        paper = await self.service.upload_pdf(file)

        self.assertEqual(paper.mime_type, "application/pdf")
        upload_kwargs = self.service.storage.upload_pdf_bytes.call_args.kwargs
        self.assertEqual(upload_kwargs["content_type"], "application/pdf")
        self.assertTrue(upload_kwargs["object_name"].endswith(".PDF"))

    async def test_upload_pdf_rejects_missing_filename(self) -> None:
        file = make_upload_file("", VALID_PDF_BYTES)

        with self.assertRaises(HTTPException) as context:
            await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Filename is required.")
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_rejects_empty_file(self) -> None:
        file = make_upload_file("empty.pdf", b"")

        with self.assertRaises(HTTPException) as context:
            await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Uploaded file is empty.")
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_rejects_invalid_pdf_signature(self) -> None:
        file = make_upload_file("invalid.pdf", b"NOT_A_PDF")

        with self.assertRaises(HTTPException) as context:
            await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Invalid PDF file signature.")
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_handles_queue_enqueue_failure(self) -> None:
        captured: dict[str, object] = {}

        def create_side_effect(paper):
            captured["paper"] = paper
            return paper

        self.service.repo.create.side_effect = create_side_effect
        self.service.queue_service.enqueue_pdf_parse.side_effect = RuntimeError("Queue unavailable")
        self.service.repo.get_by_id.side_effect = lambda _paper_id: captured.get("paper")

        file = make_upload_file("valid.pdf", VALID_PDF_BYTES)
        paper = await self.service.upload_pdf(file)

        self.assertEqual(paper.processing_status, "failed")
        self.assertEqual(paper.processing_stage, "uploaded")
        self.assertIn("Failed to enqueue parse job", paper.processing_error or "")
        self.service.activity_service.log_parse_queue_failed.assert_called_once()
        self.db.rollback.assert_called()

    async def test_upload_pdf_rejects_corrupted_pdf(self) -> None:
        file = make_upload_file("corrupted.pdf", b"%PDF-1.7\nthis is not a real pdf")

        with self.assertRaises(HTTPException) as context:
            await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Corrupted or unreadable PDF file.",
        )
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_rejects_file_larger_than_max_size(self) -> None:
        oversized_content = b"%PDF-" + (b"a" * 32)
        file = make_upload_file("oversized.pdf", oversized_content)

        with patch("app.services.paper_service.MAX_UPLOAD_SIZE_BYTES", 10):
            with self.assertRaises(HTTPException) as context:
                await self.service.upload_pdf(file)

        self.assertEqual(context.exception.status_code, 413)
        self.assertEqual(
            context.exception.detail,
            "File exceeds max size of 10 bytes.",
        )
        self.service.storage.upload_pdf_bytes.assert_not_called()

    async def test_upload_pdf_accepts_file_at_exact_max_size_boundary(self) -> None:
        file = make_upload_file("boundary.pdf", VALID_PDF_BYTES)

        with patch("app.services.paper_service.MAX_UPLOAD_SIZE_BYTES", len(VALID_PDF_BYTES)):
            paper = await self.service.upload_pdf(file)

        self.assertEqual(paper.file_size_bytes, len(VALID_PDF_BYTES))
        self.service.storage.upload_pdf_bytes.assert_called_once()

    def test_validate_pdf_content_rejects_pdf_without_pages(self) -> None:
        class EmptyPdf:
            pages: list[object] = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("app.services.paper_service.pdfplumber.open", return_value=EmptyPdf()):
            with self.assertRaises(HTTPException) as context:
                PaperService._validate_pdf_content(VALID_PDF_BYTES)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Corrupted or unreadable PDF file.",
        )


if __name__ == "__main__":
    unittest.main()
