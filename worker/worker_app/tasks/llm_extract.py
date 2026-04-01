import logging
from uuid import UUID

from app.core.database import SessionLocal
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
        service = LLMExtractionService(db)
        service.run_for_canonical_document(cid)
        logger.info("[LLM TASK] Completed canonical_document_id=%s", cid)
    except Exception:
        db.rollback()
        logger.exception("[LLM TASK] Error processing canonical_document_id=%s", canonical_document_id)
        raise
    finally:
        db.close()