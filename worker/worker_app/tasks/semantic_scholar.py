import logging
import sys
from uuid import UUID

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.core.queue import parse_queue
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.semantic_scholar_service import SemanticScholarService
from app.services.activity_log_service import ActivityLogService
from app.services.llm_enqueue_service import try_enqueue_llm_if_ready

logger = logging.getLogger(__name__)


def semantic_scholar_enrich(canonical_document_id: str) -> None:
    db = SessionLocal()
    activity_service = ActivityLogService(db)
    try:
        cid = UUID(canonical_document_id)
    except ValueError:
        logger.error("[SS enrich] Invalid canonical_document_id: %s", canonical_document_id)
        return

    try:
        canonical = (
            db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == cid)
            .first()
        )

        if not canonical:
            logger.error("[SS enrich] CanonicalDocument not found: %s", cid)
            return

        papers = (
            db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .all()
        )

        if not papers:
            logger.warning("[SS enrich] No PaperRecord mapped to canonical_id=%s", canonical.id)

        logger.info("[SS enrich] Start processing canonical_id=%s", canonical.id)

        # --------------------------------
        # 1. mark enriching
        # --------------------------------
        for paper in papers:
            if paper.processing_status != "failed":
                paper.processing_status = "processing"
                paper.processing_stage = "enriching"
                paper.processing_error = None

        activity_service.log_semantic_scholar_started(
            canonical_document_id=canonical.id,
            canonical_key=canonical.canonical_key,
            canonical_type=canonical.canonical_type,
            doi=canonical.doi,
        )    

        db.commit()

        # --------------------------------
        # 2. run Semantic Scholar helper
        # --------------------------------
        service = SemanticScholarService(db)
        result = service.run_for_canonical_document(canonical)

        # --------------------------------
        # 3. update paper statuses
        # --------------------------------
        if result in {"enriched", "unmatched", "skipped_already_enriched"}:
            for paper in papers:
                if paper.processing_status != "failed":
                    paper.processing_status = "processing"
                    paper.processing_stage = "enriched"
                    paper.processing_error = None

            if result == "enriched":
                activity_service.log_semantic_scholar_matched(
                    canonical_document_id=canonical.id,
                    canonical_key=canonical.canonical_key,
                    canonical_type=canonical.canonical_type,
                    doi=canonical.doi,
                    ss_paper_id=canonical.ss_paper_id,
                    title=canonical.title,
                )
            elif result == "unmatched":
                activity_service.log_semantic_scholar_unmatched(
                    canonical_document_id=canonical.id,
                    canonical_key=canonical.canonical_key,
                    canonical_type=canonical.canonical_type,
                    doi=canonical.doi,
                )
            else:  # skipped_already_enriched
                activity_service.log_semantic_scholar_skipped(
                    canonical_document_id=canonical.id,
                    canonical_key=canonical.canonical_key,
                    canonical_type=canonical.canonical_type,
                    doi=canonical.doi,
                    ss_paper_id=canonical.ss_paper_id,
                )

            db.commit()

            enqueued = try_enqueue_llm_if_ready(str(canonical.id))
            logger.info(
                "[SS enrich] try_enqueue_llm_if_ready canonical_id=%s enqueued=%s",
                canonical.id,
                enqueued,
            )

        elif result == "rate_limited":
            for paper in papers:
                if paper.processing_status != "failed":
                    paper.processing_status = "processing"
                    paper.processing_stage = "enriched"
                    paper.processing_error = None
            db.commit()
            logger.info(
                "[SS enrich] Finished without new enrichment result=%s canonical_id=%s",
                result,
                canonical.id,
            )

        else:
            logger.warning(
                "[SS enrich] Unexpected result=%s canonical_id=%s",
                result,
                canonical.id,
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
                paper.processing_stage = "enriching"
                paper.processing_error = f"Semantic Scholar enrichment failed: {str(e)}"

            activity_service.log_semantic_scholar_failed(
                canonical_document_id=cid,
                error_message=str(e),
            )

            db.commit()
        except Exception:
            db.rollback()

        logger.exception("[SS enrich] Error processing canonical_id=%s", canonical_document_id)
        raise

    finally:
        db.close()