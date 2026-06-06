import logging
import json
import os
import sys
import tempfile
import traceback
from typing import Any
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

# from app.models.document_section import DocumentSection
# from app.models.document_chunk import DocumentChunk
# from app.services.document_structure_service import DocumentStructureService

logger = logging.getLogger(__name__)

DOCLING_ARTIFACTS_PATH = os.getenv("DOCLING_ARTIFACTS_PATH")

_converter_with_tables: DocumentConverter | None = None
_converter_no_tables: DocumentConverter | None = None


def _normalize_block_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _label_value(item: Any) -> str:
    label = getattr(item, "label", None)
    if label is None:
        return type(item).__name__
    return str(getattr(label, "value", label))


def _page_numbers_for_item(item: Any) -> list[int]:
    page_numbers: list[int] = []
    for prov in getattr(item, "prov", None) or []:
        page_no = getattr(prov, "page_no", None)
        if isinstance(page_no, int) and page_no > 0 and page_no not in page_numbers:
            page_numbers.append(page_no)
    return page_numbers


def _export_item_text(document: Any, item: Any) -> str:
    text = getattr(item, "text", None)
    if isinstance(text, str) and text.strip():
        return _normalize_block_text(text)

    export_to_markdown = getattr(item, "export_to_markdown", None)
    if callable(export_to_markdown):
        try:
            return _normalize_block_text(export_to_markdown(document))
        except Exception:
            logger.debug(
                "[docling] Failed to export item markdown type=%s",
                type(item).__name__,
                exc_info=True,
            )

    return ""


def _is_section_header(item: Any) -> bool:
    label = _label_value(item).lower()
    return label in {"section_header", "title"} or type(item).__name__ in {
        "SectionHeaderItem",
        "TitleItem",
    }


def build_docling_pages(document: Any) -> list[dict[str, Any]]:
    pages_by_number: dict[int, dict[str, Any]] = {}
    page_numbers = sorted(
        page_no
        for page_no in getattr(document, "pages", {}).keys()
        if isinstance(page_no, int) and page_no > 0
    )

    for page_no in page_numbers:
        try:
            page_text = document.export_to_markdown(page_no=page_no).strip()
        except Exception:
            logger.debug(
                "[docling] Failed to export page markdown page=%s",
                page_no,
                exc_info=True,
            )
            page_text = ""

        pages_by_number[page_no] = {
            "page": page_no,
            "text": page_text,
            "sections": [],
            "blocks": [],
        }

    current_section: str | None = None
    for item, _level in document.iterate_items(with_groups=False, traverse_pictures=False):
        item_text = _export_item_text(document, item)
        if not item_text:
            continue

        if _is_section_header(item):
            current_section = item_text

        item_pages = _page_numbers_for_item(item)
        if not item_pages:
            continue

        label = _label_value(item)
        for page_no in item_pages:
            page = pages_by_number.setdefault(
                page_no,
                {
                    "page": page_no,
                    "text": "",
                    "sections": [],
                    "blocks": [],
                },
            )
            section = current_section
            if section and section not in page["sections"]:
                page["sections"].append(section)
            page["blocks"].append(
                {
                    "page": page_no,
                    "section": section,
                    "label": label,
                    "text": item_text,
                }
            )

    pages: list[dict[str, Any]] = []
    for page_no in sorted(pages_by_number):
        page = pages_by_number[page_no]
        if not page["text"] and page["blocks"]:
            page["text"] = "\n\n".join(
                block["text"]
                for block in page["blocks"]
                if block.get("text")
            ).strip()
        if page["text"] or page["blocks"]:
            pages.append(page)

    return pages

def get_docling_converter(do_table_structure: bool = True) -> DocumentConverter:
    global _converter_with_tables, _converter_no_tables

    if do_table_structure:
        if _converter_with_tables is None:
            pipeline_options = PdfPipelineOptions()
            if DOCLING_ARTIFACTS_PATH:
                pipeline_options.artifacts_path = DOCLING_ARTIFACTS_PATH
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True
            
            _converter_with_tables = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                }
            )
        return _converter_with_tables
    else:
        if _converter_no_tables is None:
            pipeline_options = PdfPipelineOptions()
            if DOCLING_ARTIFACTS_PATH:
                pipeline_options.artifacts_path = DOCLING_ARTIFACTS_PATH
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = False
            
            _converter_no_tables = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                }
            )
        return _converter_no_tables


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

        import pypdfium2 as pdfium
        do_table_structure = True
        try:
            pdf = pdfium.PdfDocument(tmp_pdf_path)
            page_count = len(pdf)
            pdf.close()
            logger.info("[docling] PDF page count: %s", page_count)
            if page_count > 70:
                logger.info(
                    "[docling] PDF page count (%s) exceeds threshold (70). Disabling table structure to prevent OOM.",
                    page_count,
                )
                do_table_structure = False
        except Exception as pe:
            logger.warning("[docling] Failed to read page count via pypdfium2: %s", pe)

        converter = get_docling_converter(do_table_structure=do_table_structure)
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

        docling_pages = build_docling_pages(result.document)

        md_bytes = markdown.encode("utf-8")
        md_object_name = f"papers/{paper.id}/docling.md"

        md_storage_path = storage.upload_file_bytes(
            object_name=md_object_name,
            content=md_bytes,
            content_type="text/markdown; charset=utf-8",
        )

        pages_object_name = f"papers/{paper.id}/docling_pages.json"
        pages_storage_path = storage.upload_file_bytes(
            object_name=pages_object_name,
            content=json.dumps(docling_pages, ensure_ascii=False).encode("utf-8"),
            content_type="application/json; charset=utf-8",
        )

        if hasattr(paper, "extracted_text_preview"):
            paper.extracted_text_preview = markdown[:5000]

        if hasattr(paper, "docling_markdown_storage_path"):
            paper.docling_markdown_storage_path = md_storage_path
        if hasattr(paper, "docling_page_text_json_storage_path"):
            paper.docling_page_text_json_storage_path = pages_storage_path

        # sections_count = 0
        # chunks_count = 0

        # if paper.canonical_document_id:
        #     structure_service = DocumentStructureService()

        #     # Xóa dữ liệu cũ để rebuild
        #     db.query(DocumentChunk).filter(
        #         DocumentChunk.canonical_document_id == paper.canonical_document_id
        #     ).delete(synchronize_session=False)

        #     db.query(DocumentSection).filter(
        #         DocumentSection.canonical_document_id == paper.canonical_document_id
        #     ).delete(synchronize_session=False)

        #     # Tạo sections từ markdown
        #     sections = structure_service.parse_markdown_to_sections(
        #         canonical_document_id=paper.canonical_document_id,
        #         markdown=markdown,
        #     )

        #     if sections:
        #         db.add_all(sections)
        #         db.flush()  # cần để mỗi section có id trước khi build chunks

        #         chunks = structure_service.build_chunks_from_sections(
        #             canonical_document_id=paper.canonical_document_id,
        #             sections=sections,
        #         )

        #         if chunks:
        #             from app.services.embedding_service import EmbeddingService
        #             embedding_svc = EmbeddingService()
                    
        #             # Tạo danh sách các văn bản cần tính vector
        #             texts_to_embed = [chunk.content for chunk in chunks]
                    
        #             # Tính vector nhúng theo lô (batch)
        #             embeddings = embedding_svc.generate_embeddings(texts_to_embed)
                    
        #             # Gán vector vào mỗi chunk
        #             for chunk, emb in zip(chunks, embeddings):
        #                 chunk.embedding = emb

        #             db.add_all(chunks)

        #         sections_count = len(sections)
        #         chunks_count = len(chunks)

        db.commit()

        logger.info(
            "[docling] Finished extraction for paper_id=%s, markdown_chars=%s, md_storage_path=%s, docling_pages_path=%s, pages=%s",
            paper_uuid,
            len(markdown),
            md_storage_path,
            pages_storage_path,
            len(docling_pages),
        )

        queue_service = QueueService()
        # queue_service.enqueue_llm_extract(str(paper.canonical_document_id))
        logger.info("[docling] NEW CODE PATH reached for paper_id=%s", paper_uuid)
        enqueued = False
        if paper.canonical_document_id:
            queue_service.enqueue_build_structure(str(paper.canonical_document_id))
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
