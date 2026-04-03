from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.models.paper_record import PaperRecord
from app.schemas.extraction import (
    ExtractionRunListItemResponse,
    ExtractionRunResponse,
)

router = APIRouter(prefix="/extraction-runs", tags=["extraction-runs"])


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

    return extraction


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

    return extraction