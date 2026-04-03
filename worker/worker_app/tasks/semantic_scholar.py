import logging
import sys
from uuid import UUID

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.core.queue import parse_queue
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.semantic_scholar_service import SemanticScholarService

logger = logging.getLogger(__name__)


def semantic_scholar_enrich(canonical_document_id: str) -> None:
    db = SessionLocal()

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
            db.commit()

            parse_queue.enqueue(
                "worker_app.tasks.llm_extract.llm_extract",
                str(canonical.id),
            )
            logger.info("[SS enrich] Enqueued LLM extraction for canonical_id=%s", canonical.id)

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

            db.commit()
        except Exception:
            db.rollback()

        logger.exception("[SS enrich] Error processing canonical_id=%s", canonical_document_id)
        raise

    finally:
        db.close()