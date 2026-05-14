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


        docling_ready = any(
            getattr(p, "docling_markdown_storage_path", None)
            for p in papers
        )
        if not docling_ready:
            logger.info(
                "[LLM TASK] Skip canonical_document_id=%s because docling markdown not ready",
                cid,
            )
            return

        # Guard 2: semantic should be ready first
        semantic_ready = any(
            p.processing_stage in {"enriched", "llm_extracting", "llm_extracted"}
            or p.processing_status == "completed"
            for p in papers
            if p.processing_status != "failed"
        )
        if not semantic_ready:
            logger.info(
                "[LLM TASK] Skip canonical_document_id=%s because semantic enrichment not ready",
                cid,
            )
            return

        # Guard 3: avoid duplicate run
        already_running = any(
            p.processing_status == "processing" and p.processing_stage == "llm_extracting"
            for p in papers
        )
        if already_running:
            logger.info(
                "[LLM TASK] Skip canonical_document_id=%s because extraction is already running",
                cid,
            )
            return

        already_done = all(
            p.processing_stage == "llm_extracted" or p.processing_status == "completed"
            for p in papers
            if p.processing_status != "failed"
        )
        if already_done:
            logger.info(
                "[LLM TASK] Skip canonical_document_id=%s because extraction already completed",
                cid,
            )
            return


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

        try:
            from app.services.queue_service import QueueService

            QueueService(db).enqueue_citation_graph_for_canonical(str(canonical.id))

            for paper in papers:
                can_update_status = (
                    paper.processing_status != "failed"
                    or paper.processing_stage in {"llm_extracting", "llm_extracted", "citation_scoring"}
                )
                if can_update_status:
                    paper.processing_status = "processing"
                    paper.processing_stage = "citation_scoring"
                    paper.processing_error = None

            db.commit()

            logger.info(
                "[LLM TASK] Enqueued citation graph scoring canonical_document_id=%s",
                canonical.id,
            )
        except Exception as enqueue_error:
            db.rollback()
            logger.warning(
                "[LLM TASK] Failed to enqueue citation graph scoring canonical_document_id=%s error=%s",
                canonical.id,
                str(enqueue_error),
            )

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
