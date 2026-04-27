# pyright: reportMissingImports=false

import logging
import sys
from uuid import UUID

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.models.paper_record import PaperRecord
from app.services.citation_graph_service import CitationGraphService

logger = logging.getLogger(__name__)


def _load_papers_for_canonicals(db, canonical_ids: list[UUID]) -> list[PaperRecord]:
    if not canonical_ids:
        return []

    return (
        db.query(PaperRecord)
        .filter(PaperRecord.canonical_document_id.in_(canonical_ids))
        .all()
    )


def _mark_citation_scoring(db, canonical_ids: list[UUID]) -> None:
    papers = _load_papers_for_canonicals(db, canonical_ids)
    if not papers:
        return

    for paper in papers:
        if paper.processing_status == "failed":
            continue

        paper.processing_status = "processing"
        paper.processing_stage = "citation_scoring"
        paper.processing_error = None

    db.commit()


def _mark_citation_scored(db, canonical_ids: list[UUID]) -> None:
    papers = _load_papers_for_canonicals(db, canonical_ids)
    if not papers:
        return

    for paper in papers:
        can_update = (
            paper.processing_status != "failed"
            or paper.processing_stage == "citation_scoring"
        )
        if not can_update:
            continue

        paper.processing_status = "completed"
        paper.processing_stage = "citation_scored"
        paper.processing_error = None

    db.commit()


def _mark_citation_failed(db, canonical_ids: list[UUID], error_message: str) -> None:
    papers = _load_papers_for_canonicals(db, canonical_ids)
    if not papers:
        return

    for paper in papers:
        can_update = (
            paper.processing_status != "failed"
            or paper.processing_stage == "citation_scoring"
        )
        if not can_update:
            continue

        paper.processing_status = "failed"
        paper.processing_stage = "citation_scoring"
        paper.processing_error = f"Citation scoring failed: {error_message}"

    db.commit()


def _parse_source_ids(source_canonical_ids: list[str] | None) -> list[UUID]:
    source_ids: list[UUID] = []
    seen: set[UUID] = set()

    for raw in source_canonical_ids or []:
        try:
            parsed = UUID(str(raw))
        except ValueError:
            logger.warning("[CITATION GRAPH TASK] Skip invalid source canonical id=%s", raw)
            continue

        if parsed in seen:
            continue

        seen.add(parsed)
        source_ids.append(parsed)

    return source_ids


def score_citation_graph_global(algorithm_version: str | None = None) -> None:
    db = SessionLocal()
    try:
        canonical_rows = (
            db.query(PaperRecord.canonical_document_id)
            .filter(PaperRecord.canonical_document_id.isnot(None))
            .distinct()
            .all()
        )
        canonical_ids = [row[0] for row in canonical_rows if row and row[0] is not None]

        if canonical_ids:
            _mark_citation_scoring(db, canonical_ids)

        service = CitationGraphService(db)
        run = service.score_graph(algorithm_version=algorithm_version)

        if canonical_ids:
            _mark_citation_scored(db, canonical_ids)

        logger.info(
            "[CITATION GRAPH TASK] Completed global scoring run_id=%s mentions=%s edges=%s",
            run.id,
            run.processed_mentions,
            run.processed_edges,
        )
    except Exception as exc:
        db.rollback()
        if "canonical_ids" in locals() and canonical_ids:
            try:
                _mark_citation_failed(db, canonical_ids, str(exc))
            except Exception:
                db.rollback()

        logger.exception("[CITATION GRAPH TASK] Failed global scoring")
        raise
    finally:
        db.close()


def score_citation_graph_for_canonical(
    canonical_document_id: str,
    algorithm_version: str | None = None,
) -> None:
    db = SessionLocal()
    canonical_ids: list[UUID] = []
    try:
        try:
            canonical_id = UUID(canonical_document_id)
        except ValueError:
            logger.error(
                "[CITATION GRAPH TASK] Invalid canonical_document_id=%s",
                canonical_document_id,
            )
            return

        canonical_ids = [canonical_id]
        _mark_citation_scoring(db, canonical_ids)

        service = CitationGraphService(db)
        run = service.score_graph(
            algorithm_version=algorithm_version,
            source_canonical_ids=[canonical_id],
        )

        _mark_citation_scored(db, canonical_ids)

        logger.info(
            "[CITATION GRAPH TASK] Completed canonical scoring canonical_id=%s run_id=%s mentions=%s edges=%s",
            canonical_id,
            run.id,
            run.processed_mentions,
            run.processed_edges,
        )
    except Exception as exc:
        db.rollback()
        if canonical_ids:
            try:
                _mark_citation_failed(db, canonical_ids, str(exc))
            except Exception:
                db.rollback()

        logger.exception(
            "[CITATION GRAPH TASK] Failed canonical scoring canonical_document_id=%s",
            canonical_document_id,
        )
        raise
    finally:
        db.close()


def score_citation_graph_for_sources(
    source_canonical_ids: list[str] | None,
    algorithm_version: str | None = None,
) -> None:
    db = SessionLocal()
    source_ids: list[UUID] = []
    try:
        source_ids = _parse_source_ids(source_canonical_ids)
        if not source_ids:
            logger.warning("[CITATION GRAPH TASK] No valid source canonical ids provided.")
            return

        _mark_citation_scoring(db, source_ids)

        service = CitationGraphService(db)
        run = service.score_graph(
            algorithm_version=algorithm_version,
            source_canonical_ids=source_ids,
        )

        _mark_citation_scored(db, source_ids)

        logger.info(
            "[CITATION GRAPH TASK] Completed source-list scoring run_id=%s source_count=%s mentions=%s edges=%s",
            run.id,
            len(source_ids),
            run.processed_mentions,
            run.processed_edges,
        )
    except Exception as exc:
        db.rollback()
        if source_ids:
            try:
                _mark_citation_failed(db, source_ids, str(exc))
            except Exception:
                db.rollback()

        logger.exception("[CITATION GRAPH TASK] Failed source-list scoring")
        raise
    finally:
        db.close()
