import os
import sys
import types
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKER_DIR = PROJECT_ROOT / "worker"
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from worker_app.tasks import pdf_parse as pdf_parse_task


class FakeQuery:
    def __init__(self, db: "FakeDB", model_name: str):
        self.db = db
        self.model_name = model_name

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        results = self.db.first_results.get(self.model_name, [])
        if not results:
            return None
        return results.pop(0)


class FakeDB:
    def __init__(self, first_results: dict[str, list[object]]):
        self.first_results = first_results
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def query(self, model):
        return FakeQuery(self, model.__name__)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeStorageService:
    def download_object(self, object_name: str) -> bytes:
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"

    def upload_file_bytes(self, **kwargs) -> str:
        return "s3://papers/papers/sample/pages.json"


class DummyQueue:
    def __init__(self):
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def enqueue(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class PdfParseCanonicalMappingTests(unittest.TestCase):
    def _make_paper(self) -> PaperRecord:
        return PaperRecord(
            id=uuid4(),
            original_filename="paper.pdf",
            storage_path="s3://papers/papers/sample.pdf",
            mime_type="application/pdf",
            file_size_bytes=100,
            file_hash_sha256="a" * 64,
            upload_source="portal",
            processing_status="pending",
            processing_stage="queued",
            publication_status="draft",
        )

    def test_pdf_parse_uses_doi_for_canonical_and_non_duplicate(self) -> None:
        paper = self._make_paper()
        fake_db = FakeDB(
            first_results={
                "PaperRecord": [paper, paper],
                "CanonicalDocument": [None],
            }
        )

        parse_queue = DummyQueue()
        docling_queue = DummyQueue()
        fake_queue_module = types.ModuleType("app.core.queue")
        fake_queue_module.parse_queue = parse_queue
        fake_queue_module.docling_queue = docling_queue

        with (
            patch.object(pdf_parse_task, "SessionLocal", return_value=fake_db),
            patch.object(pdf_parse_task, "StorageService", return_value=FakeStorageService()),
            patch.object(pdf_parse_task, "ActivityLogService", return_value=Mock()),
            patch.object(
                pdf_parse_task,
                "extract_pdf_text_and_preview",
                return_value=("full text body", "preview"),
            ),
            patch.object(
                pdf_parse_task,
                "extract_pdf_text_for_llm",
                return_value=("llm full text", "llm preview", [{"page": 1, "text": "sample"}]),
            ),
            patch.object(pdf_parse_task, "detect_doi", return_value="10.1000/xyz"),
            patch.object(pdf_parse_task, "detect_title", return_value="Sample Title"),
            patch.object(pdf_parse_task, "build_fingerprint") as build_fingerprint_mock,
            patch.dict(sys.modules, {"app.core.queue": fake_queue_module}),
        ):
            pdf_parse_task.pdf_parse(str(paper.id))

        self.assertEqual(paper.detected_doi, "10.1000/xyz")
        self.assertIsNone(paper.detected_fingerprint)
        self.assertFalse(paper.is_duplicate)
        self.assertIsNone(paper.duplicate_of_paper_id)
        self.assertIsNotNone(paper.canonical_document_id)
        build_fingerprint_mock.assert_not_called()

        self.assertEqual(len(fake_db.added), 1)
        created_canonical = fake_db.added[0]
        self.assertEqual(created_canonical.canonical_key, "10.1000/xyz")
        self.assertEqual(created_canonical.canonical_type, "doi")
        self.assertIsNone(created_canonical.fingerprint)
        self.assertEqual(created_canonical.title_candidate, "Sample Title")

        self.assertEqual(len(parse_queue.calls), 1)
        self.assertEqual(len(docling_queue.calls), 1)

    def test_pdf_parse_uses_fingerprint_and_marks_duplicate(self) -> None:
        paper = self._make_paper()
        existing_canonical = CanonicalDocument(
            id=uuid4(),
            canonical_key="fingerprint-123",
            canonical_type="fingerprint",
            fingerprint="fingerprint-123",
            title_candidate="Existing",
        )
        first_paper = self._make_paper()
        first_paper.canonical_document_id = existing_canonical.id

        fake_db = FakeDB(
            first_results={
                "PaperRecord": [paper, first_paper],
                "CanonicalDocument": [existing_canonical],
            }
        )

        parse_queue = DummyQueue()
        docling_queue = DummyQueue()
        fake_queue_module = types.ModuleType("app.core.queue")
        fake_queue_module.parse_queue = parse_queue
        fake_queue_module.docling_queue = docling_queue

        with (
            patch.object(pdf_parse_task, "SessionLocal", return_value=fake_db),
            patch.object(pdf_parse_task, "StorageService", return_value=FakeStorageService()),
            patch.object(pdf_parse_task, "ActivityLogService", return_value=Mock()),
            patch.object(
                pdf_parse_task,
                "extract_pdf_text_and_preview",
                return_value=("full text body", "preview"),
            ),
            patch.object(
                pdf_parse_task,
                "extract_pdf_text_for_llm",
                return_value=("llm full text", "llm preview", [{"page": 1, "text": "sample"}]),
            ),
            patch.object(pdf_parse_task, "detect_doi", return_value=None),
            patch.object(pdf_parse_task, "detect_title", return_value="Title Without Doi"),
            patch.object(pdf_parse_task, "build_fingerprint", return_value="fingerprint-123") as build_fingerprint_mock,
            patch.dict(sys.modules, {"app.core.queue": fake_queue_module}),
        ):
            pdf_parse_task.pdf_parse(str(paper.id))

        self.assertIsNone(paper.detected_doi)
        self.assertEqual(paper.detected_fingerprint, "fingerprint-123")
        self.assertEqual(paper.canonical_document_id, existing_canonical.id)
        self.assertTrue(paper.is_duplicate)
        self.assertEqual(paper.duplicate_of_paper_id, first_paper.id)
        build_fingerprint_mock.assert_called_once()

        self.assertEqual(len(fake_db.added), 0)
        self.assertEqual(len(parse_queue.calls), 1)
        self.assertEqual(len(docling_queue.calls), 0)


if __name__ == "__main__":
    unittest.main()
