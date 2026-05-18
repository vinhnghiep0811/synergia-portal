from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.queue import redis_conn
from app.models.canonical_document import CanonicalDocument
from app.models.citation_edge import CitationEdge
from app.models.citation_mention import CitationMention
from app.models.citation_score_run import CitationScoreRun
from app.schemas.citation_graph import (
    CanonicalDocumentCitationSummaryResponse,
    CitationEdgeListResponse,
    CitationNetworkEdgeResponse,
    CitationNetworkNodeResponse,
    CitationNetworkResponse,
    CitationEdgeResponse,
    CitationMentionListResponse,
    CitationMentionResponse,
    CitationQueueJobStatusResponse,
    CitationScoreEnqueueResponse,
    CitationScoreRequest,
    CitationScoreRunResponse,
)
from app.services.citation_graph_service import CitationGraphService
from app.services.queue_service import QueueService

router = APIRouter(prefix="/citation-graph", tags=["citation-graph"])


def _to_run_response(run: CitationScoreRun) -> CitationScoreRunResponse:
    return CitationScoreRunResponse.model_validate(run)


def _to_canonical_summary(
    doc: CanonicalDocument | None,
) -> CanonicalDocumentCitationSummaryResponse | None:
    if not doc:
        return None

    return CanonicalDocumentCitationSummaryResponse.model_validate(doc)


def _to_edge_response(edge: CitationEdge) -> CitationEdgeResponse:
    return CitationEdgeResponse(
        id=edge.id,
        run_id=edge.run_id,
        algorithm_version=edge.algorithm_version,
        source_canonical_id=edge.source_canonical_id,
        target_canonical_id=edge.target_canonical_id,
        source_document=_to_canonical_summary(edge.source_canonical_document),
        target_document=_to_canonical_summary(edge.target_canonical_document),
        mention_count=edge.mention_count,
        top3_mean_score=edge.top3_mean_score,
        frequency_score=edge.frequency_score,
        diversity_score=edge.diversity_score,
        intent_edge_score=edge.intent_edge_score,
        citation_score=edge.citation_score,
        score_band=edge.score_band,
        evidence_json=edge.evidence_json or [],
        updated_at=edge.updated_at,
    )


def _to_mention_response(mention: CitationMention) -> CitationMentionResponse:
    return CitationMentionResponse(
        id=mention.id,
        run_id=mention.run_id,
        source_canonical_id=mention.source_canonical_id,
        target_canonical_id=mention.target_canonical_id,
        source_chunk_id=mention.source_chunk_id,
        source_section_id=mention.source_section_id,
        anchor_text=mention.anchor_text,
        context_snippet=mention.context_snippet,
        page_from=mention.page_from,
        page_to=mention.page_to,
        section_type=mention.section_type,
        section_weight=mention.section_weight,
        link_method=mention.link_method,
        link_confidence=mention.link_confidence,
        semantic_similarity=mention.semantic_similarity,
        intent_label=mention.intent_label,
        intent_score=mention.intent_score,
        chunk_quality=mention.chunk_quality,
        mention_score=mention.mention_score,
        is_internal=mention.is_internal,
        created_at=mention.created_at,
        target_document=_to_canonical_summary(mention.target_canonical_document),
    )


def _raise_paper_lookup_error(error: ValueError) -> None:
    detail = str(error)
    if detail == "Paper not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if "has not been linked" in detail:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _ensure_canonical_exists(db: Session, canonical_document_id: UUID) -> None:
    exists = (
        db.query(CanonicalDocument.id)
        .filter(CanonicalDocument.id == canonical_document_id)
        .first()
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical document not found.",
        )


@router.post(
    "/runs/score",
    response_model=CitationScoreEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Chay citation graph scoring",
)
def score_citation_graph(
    payload: CitationScoreRequest,
    db: Session = Depends(get_db),
):
    queue_service = QueueService(db)

    canonical_ids = payload.source_canonical_ids or []

    if canonical_ids and not payload.force_full_rebuild:
        unique_ids = list(dict.fromkeys(canonical_ids))

        existing_rows = (
            db.query(CanonicalDocument.id)
            .filter(CanonicalDocument.id.in_(unique_ids))
            .all()
        )
        existing_ids = {row[0] for row in existing_rows}
        if not existing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No canonical documents found for the provided source ids.",
            )

        source_ids = [item for item in unique_ids if item in existing_ids]

        job = queue_service.enqueue_citation_graph_for_sources(
            source_canonical_ids=[str(item) for item in source_ids],
            algorithm_version=payload.algorithm_version,
        )

        return CitationScoreEnqueueResponse(
            message="Citation graph scoring job queued for selected canonical documents.",
            queued_job_id=job.id,
            algorithm_version=payload.algorithm_version,
            source_canonical_ids=source_ids,
        )

    job = queue_service.enqueue_citation_graph_global(
        algorithm_version=payload.algorithm_version,
    )

    return CitationScoreEnqueueResponse(
        message=(
            "Citation graph full rebuild job queued."
            if payload.force_full_rebuild
            else "Citation graph global scoring job queued."
        ),
        queued_job_id=job.id,
        algorithm_version=payload.algorithm_version,
        source_canonical_ids=None,
    )


@router.post(
    "/runs/score/by-paper/{paper_id}",
    response_model=CitationScoreEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Chay citation graph scoring cho paper",
)
def score_citation_graph_by_paper(
    paper_id: UUID,
    algorithm_version: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)
    queue_service = QueueService(db)

    try:
        canonical_id = service.get_canonical_id_by_paper_id(paper_id)
    except ValueError as error:
        _raise_paper_lookup_error(error)

    job = queue_service.enqueue_citation_graph_for_canonical(
        canonical_document_id=str(canonical_id),
        algorithm_version=algorithm_version,
    )

    return CitationScoreEnqueueResponse(
        message="Citation graph scoring job queued for paper canonical document.",
        queued_job_id=job.id,
        algorithm_version=algorithm_version,
        source_canonical_ids=[canonical_id],
        paper_id=paper_id,
    )


@router.get(
    "/runs/latest",
    response_model=CitationScoreRunResponse,
    summary="Lay run citation graph moi nhat",
)
def get_latest_citation_score_run(
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)
    run = service.get_latest_completed_run()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed citation score run found.",
        )

    return _to_run_response(run)


@router.get(
    "/runs/{run_id}",
    response_model=CitationScoreRunResponse,
    summary="Lay chi tiet citation score run",
)
def get_citation_score_run(
    run_id: UUID,
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)
    run = service.get_run(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found.",
        )

    return _to_run_response(run)


@router.get(
    "/network",
    response_model=CitationNetworkResponse,
    summary="Lay citation network toan cuc",
)
def get_citation_network(
    run_id: UUID | None = Query(default=None),
    limit_edges: int = Query(default=300, ge=1, le=1000),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    include_all_documents: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)
    run, edges = service.list_network(
        run_id=run_id,
        limit_edges=limit_edges,
        min_score=min_score,
    )

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found or not completed.",
        )

    node_map: dict[UUID, CitationNetworkNodeResponse] = {}

    def _ensure_node(canonical_document_id: UUID, doc: CanonicalDocument | None) -> CitationNetworkNodeResponse:
        existing = node_map.get(canonical_document_id)
        if existing:
            return existing

        node = CitationNetworkNodeResponse(
            canonical_document_id=canonical_document_id,
            title=doc.title if doc else None,
            publication_year=doc.publication_year if doc else None,
            doi=doc.doi if doc else None,
            out_degree=0,
            in_degree=0,
        )
        node_map[canonical_document_id] = node
        return node

    edge_items: list[CitationNetworkEdgeResponse] = []
    for edge in edges:
        source_node = _ensure_node(edge.source_canonical_id, edge.source_canonical_document)
        target_node = _ensure_node(edge.target_canonical_id, edge.target_canonical_document)

        source_node.out_degree += 1
        target_node.in_degree += 1

        edge_items.append(
            CitationNetworkEdgeResponse(
                edge_id=edge.id,
                source_canonical_id=edge.source_canonical_id,
                target_canonical_id=edge.target_canonical_id,
                source_title=edge.source_canonical_document.title if edge.source_canonical_document else None,
                target_title=edge.target_canonical_document.title if edge.target_canonical_document else None,
                citation_score=edge.citation_score,
                mention_count=edge.mention_count,
                score_band=edge.score_band,
            )
        )

    run_meta: dict[str, object] = {}
    if isinstance(run.weights_json, dict):
        raw_meta = run.weights_json.get("_run_meta")
        if isinstance(raw_meta, dict):
            run_meta = raw_meta

    scoped_source_ids: set[UUID] = set()
    raw_source_ids = run_meta.get("source_canonical_ids")
    if isinstance(raw_source_ids, list):
        for item in raw_source_ids:
            try:
                scoped_source_ids.add(UUID(str(item)))
            except (TypeError, ValueError):
                continue

    doc_query = db.query(CanonicalDocument)
    if scoped_source_ids and not include_all_documents:
        doc_query = doc_query.filter(CanonicalDocument.id.in_(scoped_source_ids))

    canonical_docs = doc_query.all()
    for doc in canonical_docs:
        _ensure_node(doc.id, doc)

    nodes = sorted(
        node_map.values(),
        key=lambda item: (item.out_degree + item.in_degree, item.title or ""),
        reverse=True,
    )

    return CitationNetworkResponse(
        run=_to_run_response(run),
        total_nodes=len(nodes),
        total_edges=len(edge_items),
        nodes=nodes,
        edges=edge_items,
    )


@router.get(
    "/canonical/{canonical_document_id}/outgoing",
    response_model=CitationEdgeListResponse,
    summary="Lay citation edges outgoing",
)
def get_outgoing_edges(
    canonical_document_id: UUID,
    run_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    _ensure_canonical_exists(db, canonical_document_id)

    service = CitationGraphService(db)
    run, edges = service.list_edges(
        canonical_document_id=canonical_document_id,
        direction="outgoing",
        run_id=run_id,
        limit=limit,
        min_score=min_score,
    )

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found or not completed.",
        )

    return CitationEdgeListResponse(
        run=_to_run_response(run),
        direction="outgoing",
        canonical_document_id=canonical_document_id,
        items=[_to_edge_response(edge) for edge in edges],
    )


@router.get(
    "/canonical/{canonical_document_id}/incoming",
    response_model=CitationEdgeListResponse,
    summary="Lay citation edges incoming",
)
def get_incoming_edges(
    canonical_document_id: UUID,
    run_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    _ensure_canonical_exists(db, canonical_document_id)

    service = CitationGraphService(db)
    run, edges = service.list_edges(
        canonical_document_id=canonical_document_id,
        direction="incoming",
        run_id=run_id,
        limit=limit,
        min_score=min_score,
    )

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found or not completed.",
        )

    return CitationEdgeListResponse(
        run=_to_run_response(run),
        direction="incoming",
        canonical_document_id=canonical_document_id,
        items=[_to_edge_response(edge) for edge in edges],
    )


@router.get(
    "/by-paper/{paper_id}/outgoing",
    response_model=CitationEdgeListResponse,
    summary="Lay citation edges outgoing theo paper",
)
def get_outgoing_edges_by_paper(
    paper_id: UUID,
    run_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)

    try:
        canonical_document_id = service.get_canonical_id_by_paper_id(paper_id)
    except ValueError as error:
        _raise_paper_lookup_error(error)

    run, edges = service.list_edges(
        canonical_document_id=canonical_document_id,
        direction="outgoing",
        run_id=run_id,
        limit=limit,
        min_score=min_score,
    )

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found or not completed.",
        )

    return CitationEdgeListResponse(
        run=_to_run_response(run),
        direction="outgoing",
        canonical_document_id=canonical_document_id,
        items=[_to_edge_response(edge) for edge in edges],
    )


@router.get(
    "/by-paper/{paper_id}/incoming",
    response_model=CitationEdgeListResponse,
    summary="Lay citation edges incoming theo paper",
)
def get_incoming_edges_by_paper(
    paper_id: UUID,
    run_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)

    try:
        canonical_document_id = service.get_canonical_id_by_paper_id(paper_id)
    except ValueError as error:
        _raise_paper_lookup_error(error)

    run, edges = service.list_edges(
        canonical_document_id=canonical_document_id,
        direction="incoming",
        run_id=run_id,
        limit=limit,
        min_score=min_score,
    )

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation score run not found or not completed.",
        )

    return CitationEdgeListResponse(
        run=_to_run_response(run),
        direction="incoming",
        canonical_document_id=canonical_document_id,
        items=[_to_edge_response(edge) for edge in edges],
    )


@router.get(
    "/edges/{edge_id}/mentions",
    response_model=CitationMentionListResponse,
    summary="Lay citation mentions cua edge",
)
def get_edge_mentions(
    edge_id: UUID,
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    service = CitationGraphService(db)
    edge, mentions = service.list_mentions_for_edge(edge_id=edge_id, limit=limit)

    if not edge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation edge not found.",
        )

    return CitationMentionListResponse(
        edge=_to_edge_response(edge),
        items=[_to_mention_response(item) for item in mentions],
    )


@router.get(
    "/jobs/{job_id}/status",
    response_model=CitationQueueJobStatusResponse,
    summary="Lay trang thai queue job citation graph",
)
def get_citation_job_status(
    job_id: str,
):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation graph queue job not found.",
        )

    error_excerpt = None
    if job.exc_info:
        error_excerpt = job.exc_info[-1200:]

    return CitationQueueJobStatusResponse(
        job_id=job.id,
        status=job.get_status(refresh=True) or "unknown",
        enqueued_at=job.enqueued_at,
        started_at=job.started_at,
        ended_at=job.ended_at,
        error_excerpt=error_excerpt,
    )
