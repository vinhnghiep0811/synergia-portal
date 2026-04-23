import logging
import os
import sys
import tempfile
import traceback
from uuid import UUID

sys.path.append("/backend")

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from app.services.llm_enqueue_service import try_enqueue_llm_if_ready

from app.core.database import SessionLocal
from app.models.paper_record import PaperRecord
from app.services.queue_service import QueueService
from app.services.storage_service import StorageService

from app.models.document_section import DocumentSection
from app.models.document_chunk import DocumentChunk
from app.services.document_structure_service import DocumentStructureService

logger = logging.getLogger(__name__)

DOCLING_ARTIFACTS_PATH = os.getenv("DOCLING_ARTIFACTS_PATH")

_converter: DocumentConverter | None = None

def build_docling_converter() -> DocumentConverter:
    global _converter

    if _converter is not None:
        return _converter

    pipeline_options = PdfPipelineOptions()
    if DOCLING_ARTIFACTS_PATH:
        pipeline_options.artifacts_path = DOCLING_ARTIFACTS_PATH
    pipeline_options.do_ocr = False

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )
    return _converter


def extract_docling_text(paper_id: str) -> None:
    db = SessionLocal()
    tmp_pdf_path: str | None = None
    paper_uuid: UUID | None = None

    try:
        try:
            paper_uuid = UUID(paper_id)
        except ValueError:
            logger.error("[docling] Invalid paper_id=%s", paper_id)
            return

        paper = db.query(PaperRecord).filter(PaperRecord.id == paper_uuid).first()
        if not paper:
            logger.error("[docling] Paper not found: %s", paper_uuid)
            return

        logger.info("[docling] Start extraction for paper_id=%s", paper_uuid)

        storage = StorageService()
        pdf_bytes = storage.download_by_storage_path(paper.storage_path)

        if not pdf_bytes:
            raise ValueError("Downloaded PDF is empty")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(pdf_bytes)
            tmp_pdf_path = tmp_pdf.name

        converter = build_docling_converter()
        try:
            result = converter.convert(tmp_pdf_path)
        except Exception as e:
            logger.error(
                "[docling] convert error type=%s, message=%s",
                type(e).__name__,
                str(e),
            )
            logger.error("[docling] full traceback:\n%s", traceback.format_exc())
            raise

        if result is None or result.document is None:
            raise ValueError("Docling conversion returned no document")

        markdown = result.document.export_to_markdown()
        if not markdown or not markdown.strip():
            raise ValueError("Docling returned empty markdown")

        md_bytes = markdown.encode("utf-8")
        md_object_name = f"papers/{paper.id}/docling.md"

        md_storage_path = storage.upload_file_bytes(
            object_name=md_object_name,
            content=md_bytes,
            content_type="text/markdown; charset=utf-8",
        )

        if hasattr(paper, "extracted_text_preview"):
            paper.extracted_text_preview = markdown[:5000]

        if hasattr(paper, "docling_markdown_storage_path"):
            paper.docling_markdown_storage_path = md_storage_path

        sections_count = 0
        chunks_count = 0

        if paper.canonical_document_id:
            structure_service = DocumentStructureService()

            # Xóa dữ liệu cũ để rebuild
            db.query(DocumentChunk).filter(
                DocumentChunk.canonical_document_id == paper.canonical_document_id
            ).delete(synchronize_session=False)

            db.query(DocumentSection).filter(
                DocumentSection.canonical_document_id == paper.canonical_document_id
            ).delete(synchronize_session=False)

            # Tạo sections từ markdown
            sections = structure_service.parse_markdown_to_sections(
                canonical_document_id=paper.canonical_document_id,
                markdown=markdown,
            )

            if sections:
                db.add_all(sections)
                db.flush()  # cần để mỗi section có id trước khi build chunks

                chunks = structure_service.build_chunks_from_sections(
                    canonical_document_id=paper.canonical_document_id,
                    sections=sections,
                    max_chars=3000,
                )

                if chunks:
                    db.add_all(chunks)

                sections_count = len(sections)
                chunks_count = len(chunks)

        db.commit()

        logger.info(
            "[docling] Finished extraction for paper_id=%s, markdown_chars=%s, md_storage_path=%s",
            paper_uuid,
            len(markdown),
            md_storage_path,
            sections_count,
            chunks_count
        )

        # queue_service = QueueService()
        # queue_service.enqueue_llm_extract(str(paper.canonical_document_id))
        logger.info("[docling] NEW CODE PATH reached for paper_id=%s", paper_uuid)
        enqueued = False
        if paper.canonical_document_id:
            enqueued = try_enqueue_llm_if_ready(str(paper.canonical_document_id))

        logger.info(
            "[docling] try_enqueue_llm_if_ready canonical_id=%s enqueued=%s",
            paper.canonical_document_id,
            enqueued,
        )

    except Exception:
        db.rollback()
        logger.exception("[docling] Error processing paper_id=%s", paper_id)
        raise

    finally:
        db.close()

        if tmp_pdf_path and os.path.exists(tmp_pdf_path):
            os.remove(tmp_pdf_path)