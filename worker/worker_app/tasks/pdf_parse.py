import logging
import json
import os
import sys
import tempfile
from uuid import UUID
from sqlalchemy.exc import IntegrityError

sys.path.append("/backend")
from app.services.activity_log_service import ActivityLogService
from app.core.database import SessionLocal
from app.models.paper_record import PaperRecord
from app.models.canonical_document import CanonicalDocument
from app.services.storage_service import StorageService
from app.services.pdf_parse_service import (
    extract_pdf_text_and_preview,
    detect_doi,
    detect_title,
    build_fingerprint,
    extract_pdf_text_for_llm,
)

logger = logging.getLogger(__name__)

def parse_storage_path(storage_path: str) -> str:
    # s3://bucket/object_name
    return storage_path.split("/", 3)[-1]

def pdf_parse(paper_id: str) -> None:
    db = SessionLocal()
    activity_service = ActivityLogService(db)
    try:
        paper_uuid = UUID(paper_id)
    except ValueError:
        logger.error(f"[pdf_parse] Invalid paper_id: {paper_id}")
        return

    try:
        paper = (
            db.query(PaperRecord)
            .filter(PaperRecord.id == paper_uuid)
            .first()
        )

        if not paper:
            logger.error(f"[pdf_parse] Paper not found: {paper_uuid}")
            return

        logger.info(f"[pdf_parse] Start processing paper_id={paper_uuid}")

        # --------------------------------
        # 1. set status parsing
        # --------------------------------
        paper.processing_status = "processing"
        paper.processing_stage = "parsing"
        paper.processing_error = None

        activity_service.log_parse_started(
            paper_id=paper.id,
            filename=paper.original_filename,
        )

        db.commit()

        # --------------------------------
        # 2. download PDF from MinIO
        # --------------------------------
        storage = StorageService()
        object_name = parse_storage_path(paper.storage_path)

        pdf_bytes = storage.download_object(object_name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        # --------------------------------
        # 3. extract text
        # --------------------------------
        full_text, preview = extract_pdf_text_and_preview(tmp_path)

        paper.extracted_text_preview = preview

        llm_full_text, llm_preview, pages = extract_pdf_text_for_llm(tmp_path)

        pages_json_bytes = json.dumps(
            pages,
            ensure_ascii=False,
        ).encode("utf-8")

        pages_object_name = f"papers/{paper.id}/pages.json"

        pages_storage_path = storage.upload_file_bytes(
            object_name=pages_object_name,
            content=pages_json_bytes,
            content_type="application/json; charset=utf-8",
        )

        paper.page_text_json_storage_path = pages_storage_path

        # --------------------------------
        # 4. detect DOI
        # --------------------------------
        doi = detect_doi(full_text)
        paper.detected_doi = doi
        paper.detected_fingerprint = None

        # --------------------------------
        # 5. detect title
        # --------------------------------
        # logger.warning("CALLING detect_title with %s", tmp_path)

        title = detect_title(tmp_path)
        # logger.warning("DETECTED TITLE = %s", title)
        paper.detected_title = title

         # --------------------------------
        # 6. determine canonical key
        # --------------------------------
        if doi:
            canonical_key = doi
            canonical_type = "doi"
            fingerprint = None
        else:
            fingerprint = build_fingerprint(full_text, title)
            paper.detected_fingerprint = fingerprint
            canonical_key = fingerprint
            canonical_type = "fingerprint"

        # --------------------------------
        # 7. find existing canonical
        # --------------------------------
        canonical = (
            db.query(CanonicalDocument)
            .filter(CanonicalDocument.canonical_key == canonical_key)
            .first()
        )

        if not canonical:
            canonical = CanonicalDocument(
                canonical_key=canonical_key,
                canonical_type=canonical_type,
                doi=doi,
                fingerprint=fingerprint,
                title_candidate=title,
            )
            db.add(canonical)
            try:
                db.commit()
                db.refresh(canonical)
            except IntegrityError:
                db.rollback()
                canonical = (
                    db.query(CanonicalDocument)
                    .filter(CanonicalDocument.canonical_key == canonical_key)
                    .first()
                )
                if not canonical:
                    raise

        paper.canonical_document_id = canonical.id

        # --------------------------------
        # 8. duplicate detection
        # --------------------------------
        first_paper = (
            db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .order_by(PaperRecord.created_at.asc())
            .first()
        )

        if first_paper and first_paper.id != paper.id:
            paper.is_duplicate = True
            paper.duplicate_of_paper_id = first_paper.id

            activity_service.log_duplicate_detected(
                paper_id=paper.id,
                canonical_document_id=canonical.id,
                canonical_key=canonical.canonical_key,
                canonical_type=canonical.canonical_type,
                duplicate_of_paper_id=first_paper.id,
            )
        else:
            paper.is_duplicate = False
            paper.duplicate_of_paper_id = None  

        # --------------------------------
        # 9. mark parse done
        # --------------------------------
        paper.processing_status = "processing"
        paper.processing_stage = "parsed"
        paper.processing_error = None

        activity_service.log_parse_completed(
            paper_id=paper.id,
            canonical_document_id=canonical.id,
            filename=paper.original_filename,
            doi=doi,
            title=title,
            canonical_key=canonical.canonical_key,
            canonical_type=canonical.canonical_type,
        )

        db.commit()

        # --------------------------------
        # 10. enqueue Semantic Scholar enrichment
        # --------------------------------
        try:
            from app.core.queue import parse_queue, docling_queue
            parse_queue.enqueue(
                "worker_app.tasks.semantic_scholar.semantic_scholar_enrich",
                str(canonical.id)
            )
            logger.info(f"[pdf_parse] Enqueued SS enrichment for canonical_id={canonical.id}")
        except Exception as e:
            # Khong lam hong flow chinh neu enqueue that bai
            logger.warning(f"[pdf_parse] Failed to enqueue SS enrichment: {e}")

        try:
            if not paper.is_duplicate:
                docling_queue.enqueue(
                    "tasks.docling.extract_docling_text",
                    str(paper.id)
                )
                logger.info(
                    f"[pdf_parse] Enqueued Docling extraction for paper_id={paper.id}"
                )
            else:
                logger.info(
                    f"[pdf_parse] Skip Docling enqueue for duplicate paper_id={paper.id}"
                )
        except Exception as e:
            logger.warning(f"[pdf_parse] Failed to enqueue Docling extraction: {e}")

        logger.info(f"[pdf_parse] Completed paper_id={paper_uuid}")

        os.remove(tmp_path)

    except Exception as e:
        db.rollback()

        try:
            paper = (
                db.query(PaperRecord)
                .filter(PaperRecord.id == paper_uuid)
                .first()
            )
            if paper:
                paper.processing_status = "failed"
                paper.processing_stage = "parsing"
                paper.processing_error = str(e)

                activity_service.log_parse_failed(
                    paper_id=paper.id,
                    filename=paper.original_filename,
                    error_message=str(e),
                )

                db.commit()
        except Exception:
            db.rollback()

        logger.exception(f"[pdf_parse] Error processing paper_id={paper_uuid}")
        raise
    finally:
        db.close()
