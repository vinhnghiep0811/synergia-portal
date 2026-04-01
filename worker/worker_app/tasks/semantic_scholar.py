import logging
import sys
from uuid import UUID

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.core.queue import parse_queue
from app.models.canonical_document import CanonicalDocument
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

        service = SemanticScholarService(db)
        result = service.run_for_canonical_document(canonical)

        if result == "enriched":
            parse_queue.enqueue(
                "worker_app.tasks.llm_extract.llm_extract",
                str(canonical.id),
            )
            logger.info("[SS enrich] Enqueued LLM extraction for canonical_id=%s", canonical.id)

    except Exception:
        db.rollback()
        logger.exception("[SS enrich] Error processing canonical_id=%s", canonical_document_id)
        raise
    finally:
        db.close()