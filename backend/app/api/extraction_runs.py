from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.queue import parse_queue
from app.core.database import get_db
from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.models.paper_record import PaperRecord
from app.schemas.extraction import (
    ExtractionRetryResponse,
    ExtractionRunListItemResponse,
    ExtractionRunResponse,
)

router = APIRouter(prefix="/extraction-runs", tags=["extraction-runs"])

def _to_extraction_run_response(extraction: ExtractionRun) -> ExtractionRunResponse:
    return ExtractionRunResponse(
        id=extraction.id,
        canonical_document_id=extraction.canonical_document_id,
        model_name=extraction.model_name,
        prompt_version=extraction.prompt_version,
        status=extraction.status,
        problem_statement=extraction.problem_statement,
        main_method=extraction.main_method,
        contributions=extraction.contributions or [],
        limitations=extraction.limitations or [],
        evaluation_setup=extraction.evaluation_setup,
        raw_llm_response=extraction.raw_llm_response,
        token_input=extraction.token_input,
        token_output=extraction.token_output,
        created_at=extraction.created_at,
        updated_at=extraction.updated_at,
    )

@router.get(
    "/by-paper/{paper_id}",
    response_model=ExtractionRunResponse,
    summary="Lay extraction moi nhat cua mot paper",
    description="""
Tien ich cho frontend: tu paper_id lay extraction moi nhat
thong qua canonical_document_id ma khong can biet extraction_run_id truoc.
""",
    responses={
        404: {
            "description": "Paper hoac extraction khong ton tai",
            "content": {
                "application/json": {
                    "examples": {
                        "paper_not_found": {
                            "summary": "Paper not found",
                            "value": {"detail": "Paper not found."},
                        },
                        "canonical_missing": {
                            "summary": "Paper not linked to canonical",
                            "value": {
                                "detail": "Paper has not been linked to a canonical document yet."
                            },
                        },
                        "extraction_not_found": {
                            "summary": "Extraction not found",
                            "value": {"detail": "Extraction run not found."},
                        },
                    }
                }
            },
        }
    },
)
def get_latest_extraction_by_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    paper = (
        db.query(PaperRecord)
        .filter(PaperRecord.id == paper_id)
        .first()
    )
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    if not paper.canonical_document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper has not been linked to a canonical document yet.",
        )

    extraction = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.canonical_document_id == paper.canonical_document_id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction run not found.",
        )

    return _to_extraction_run_response(extraction)


@router.get(
    "/canonical/{canonical_document_id}",
    response_model=list[ExtractionRunListItemResponse],
    summary="Lay danh sach extraction runs cua mot canonical document",
    description="""
Tra ve danh sach ExtractionRun gan voi canonical document.
Huu ich de debug canonical caching va xem lich su extraction.
""",
    responses={
        404: {
            "description": "Khong tim thay canonical document",
            "content": {
                "application/json": {
                    "example": {"detail": "Canonical document not found."}
                }
            },
        }
    },
)
def list_extraction_runs_by_canonical(
    canonical_document_id: UUID,
    db: Session = Depends(get_db),
):
    canonical = (
        db.query(CanonicalDocument)
        .filter(CanonicalDocument.id == canonical_document_id)
        .first()
    )
    if not canonical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical document not found.",
        )

    extraction_runs = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.canonical_document_id == canonical_document_id)
        .order_by(ExtractionRun.created_at.desc())
        .all()
    )

    return extraction_runs


@router.get(
    "/{extraction_run_id}",
    response_model=ExtractionRunResponse,
    summary="Lay chi tiet mot extraction run",
    responses={
        404: {
            "description": "Khong tim thay extraction run",
            "content": {
                "application/json": {
                    "example": {"detail": "Extraction run not found."}
                }
            },
        }
    },
)
def get_extraction_run(
    extraction_run_id: UUID,
    db: Session = Depends(get_db),
):
    extraction = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.id == extraction_run_id)
        .first()
    )
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction run not found.",
        )

    return _to_extraction_run_response(extraction)


@router.post(
    "/by-paper/{paper_id}/retry",
    response_model=ExtractionRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry LLM extraction for a failed paper",
    responses={
        404: {
            "description": "Paper not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Paper not found."}
                }
            },
        },
        409: {
            "description": "Paper is not eligible for retry",
        },
    },
)
def retry_llm_extraction_by_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    paper = (
        db.query(PaperRecord)
        .filter(PaperRecord.id == paper_id)
        .first()
    )
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    if not paper.canonical_document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paper has not been linked to a canonical document yet.",
        )

    latest_run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.canonical_document_id == paper.canonical_document_id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )

    is_failed_llm_stage = (
        paper.processing_status == "failed"
        and paper.processing_stage == "llm_extracting"
    )
    latest_failed = latest_run is not None and latest_run.status == "failed"

    if latest_run is not None and latest_run.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LLM extraction is already running for this canonical document.",
        )

    if not is_failed_llm_stage and not latest_failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LLM extraction is not in failed state for this paper.",
        )

    related_papers = (
        db.query(PaperRecord)
        .filter(PaperRecord.canonical_document_id == paper.canonical_document_id)
        .all()
    )
    for related_paper in related_papers:
        related_paper.processing_status = "pending"
        related_paper.processing_stage = "llm_extracting"
        related_paper.processing_error = None

    canonical = (
        db.query(CanonicalDocument)
        .filter(CanonicalDocument.id == paper.canonical_document_id)
        .first()
    )
    if canonical:
        canonical.extraction_cache_status = "pending"
        db.add(canonical)

    db.commit()

    job = parse_queue.enqueue(
        "worker_app.tasks.llm_extract.llm_extract",
        str(paper.canonical_document_id),
    )

    return ExtractionRetryResponse(
        message="LLM retry job queued successfully.",
        paper_id=paper.id,
        canonical_document_id=paper.canonical_document_id,
        queued_job_id=job.id,
    )