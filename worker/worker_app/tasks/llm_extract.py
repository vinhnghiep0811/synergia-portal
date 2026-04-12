import logging
from uuid import UUID

from app.core.database import SessionLocal
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.llm_extraction_service import LLMExtractionService
from app.services.activity_log_service import ActivityLogService

logger = logging.getLogger(__name__)


def llm_extract(canonical_document_id: str) -> None:
    db = SessionLocal()
    activity_service = ActivityLogService(db)
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
            can_update_status = (
                paper.processing_status != "failed"
                or paper.processing_stage == "llm_extracting"
            )
            if can_update_status:
                paper.processing_status = "processing"
                paper.processing_stage = "llm_extracting"
                paper.processing_error = None

        activity_service.log_llm_extraction_started(
            canonical_document_id=canonical.id,
            canonical_key=canonical.canonical_key,
            canonical_type=canonical.canonical_type,
        )

        db.commit()

        # 2. run service
        service = LLMExtractionService(db)
        result = service.run_for_canonical_document(canonical.id)

        # 3. update papers after success/cache hit
        for paper in papers:
            can_update_status = (
                paper.processing_status != "failed"
                or paper.processing_stage == "llm_extracting"
            )
            if can_update_status:
                paper.processing_status = "completed"
                paper.processing_stage = "llm_extracted"
                paper.processing_error = None

        is_cache_hit = getattr(result, "cache_hit", False)

        if is_cache_hit:
            activity_service.log_llm_extraction_cache_hit(
                canonical_document_id=canonical.id,
                extraction_run_id=result.id,
            )
        else:
            activity_service.log_llm_extraction_completed(
                canonical_document_id=canonical.id,
                extraction_run_id=result.id,
            )

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

            activity_service.log_llm_extraction_failed(
                canonical_document_id=cid,
                error_message=str(e),
            )

            db.commit()
        except Exception:
            db.rollback()

        logger.exception("[LLM TASK] Error processing canonical_document_id=%s", canonical_document_id)
        raise

    finally:
        db.close()