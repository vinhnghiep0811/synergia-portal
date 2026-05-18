import logging
from uuid import UUID

from app.core.database import SessionLocal
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.queue_service import QueueService

logger = logging.getLogger(__name__)


def try_enqueue_llm_if_ready(canonical_document_id: str) -> bool:
    db = SessionLocal()
    try:
        cid = UUID(canonical_document_id)

        canonical = (
            db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == cid)
            .first()
        )
        if not canonical:
            logger.warning("[LLM ENQUEUE] Canonical not found: %s", cid)
            return False

        papers = (
            db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .all()
        )
        if not papers:
            logger.warning("[LLM ENQUEUE] No papers for canonical_id=%s", canonical.id)
            return False

        ready_paper = next(
            (
                p for p in papers
                if getattr(p, "docling_markdown_storage_path", None)
                and getattr(p, "page_text_json_storage_path", None)
            ),
            None,
        )
        if not ready_paper:
            logger.info(
                "[LLM ENQUEUE] Docling markdown or page_text_json not ready for canonical_id=%s",
                canonical.id,
            )
            return False

        semantic_ready = any(
            p.processing_stage in {"enriched", "llm_extracting", "llm_extracted"}
            for p in papers
        )
        if not semantic_ready:
            logger.info(
                "[LLM ENQUEUE] Semantic enrichment not ready for canonical_id=%s",
                canonical.id,
            )
            return False

        already_running = any(
            p.processing_status == "processing" and p.processing_stage == "llm_extracting"
            for p in papers
        )
        if already_running:
            logger.info(
                "[LLM ENQUEUE] Skip because LLM extraction is already running for canonical_id=%s",
                canonical.id,
            )
            return False

        already_done = any(
            p.processing_stage == "llm_extracted"
            for p in papers
        )
        if already_done:
            logger.info(
                "[LLM ENQUEUE] Skip because LLM extraction already completed for canonical_id=%s",
                canonical.id,
            )
            return False

        QueueService(db).enqueue_llm_extract(str(canonical.id))
        logger.info("[LLM ENQUEUE] Enqueued LLM for canonical_id=%s", canonical.id)
        return True

    except Exception:
        logger.exception(
            "[LLM ENQUEUE] Failed for canonical_document_id=%s",
            canonical_document_id,
        )
        return False
    finally:
        db.close()
