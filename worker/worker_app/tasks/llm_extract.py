import logging
from uuid import UUID

from app.core.database import SessionLocal
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.llm_extraction_service import LLMExtractionService

logger = logging.getLogger(__name__)


def llm_extract(canonical_document_id: str) -> None:
    db = SessionLocal()

    try:
        cid = UUID(canonical_document_id)
    except ValueError:
        logger.error("[LLM TASK] Invalid canonical_document_id: %s", canonical_document_id)
        return

    try:
        canonical = (
            db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == cid)
            .first()
        )

        if not canonical:
            logger.error("[LLM TASK] CanonicalDocument not found: %s", cid)
            return

        papers = (
            db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .all()
        )

        if not papers:
            logger.warning("[LLM TASK] No PaperRecord mapped to canonical_id=%s", canonical.id)

        logger.info("[LLM TASK] Start canonical_document_id=%s", cid)

        # 1. mark extracting
        for paper in papers:
            if paper.processing_status != "failed":
                paper.processing_status = "processing"
                paper.processing_stage = "llm_extracting"
                paper.processing_error = None
        db.commit()

        # 2. run service
        service = LLMExtractionService(db)
        result = service.run_for_canonical_document(canonical.id)

        # 3. update papers after success/cache hit
        for paper in papers:
            if paper.processing_status != "failed":
                paper.processing_status = "completed"
                paper.processing_stage = "llm_extracted"
                paper.processing_error = None
        db.commit()

        logger.info(
            "[LLM TASK] Completed canonical_document_id=%s extraction_run_id=%s",
            cid,
            result.id,
        )

    except Exception as e:
        db.rollback()

        try:
            papers = (
                db.query(PaperRecord)
                .filter(PaperRecord.canonical_document_id == cid)
                .all()
            )

            for paper in papers:
                paper.processing_status = "failed"
                paper.processing_stage = "llm_extracting"
                paper.processing_error = f"LLM extraction failed: {str(e)}"

            db.commit()
        except Exception:
            db.rollback()

        logger.exception("[LLM TASK] Error processing canonical_document_id=%s", canonical_document_id)
        raise

    finally:
        db.close()