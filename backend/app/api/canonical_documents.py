from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.schemas.paper import PaperInCanonicalResponse
from app.core.database import get_db
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.schemas.canonical_document import (
    CanonicalDocumentListItemResponse,
    CanonicalDocumentResponse,
)

router = APIRouter(prefix="/canonical-documents", tags=["canonical-documents"])


@router.get(
    "",
    response_model=list[CanonicalDocumentListItemResponse],
    summary="Lay danh sach canonical documents",
    description="""
Tra ve danh sach CanonicalDocument co phan trang.
Co the loc theo enrichment_status de xem nhung paper da enrich xong
hay chua match duoc.
""",
)
def list_canonical_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    enrichment_status: str | None = Query(
        None,
        description="Loc theo trang thai: pending, enriched, unmatched",
    ),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            CanonicalDocument,
            func.count(PaperRecord.id).label("paper_count"),
        )
        .outerjoin(
            PaperRecord,
            PaperRecord.canonical_document_id == CanonicalDocument.id,
        )
    )

    if enrichment_status:
        query = query.filter(CanonicalDocument.enrichment_status == enrichment_status)

    results = (
        query.group_by(CanonicalDocument.id)
        .order_by(CanonicalDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        CanonicalDocumentListItemResponse(
            id=canonical.id,
            canonical_key=canonical.canonical_key,
            canonical_type=canonical.canonical_type,
            doi=canonical.doi,
            title=canonical.title,
            title_candidate=canonical.title_candidate,
            venue=canonical.venue,
            publication_year=canonical.publication_year,
            metadata_source=canonical.metadata_source,
            enrichment_status=canonical.enrichment_status,
            match_status=canonical.match_status,
            created_at=canonical.created_at,
            updated_at=canonical.updated_at,
            paper_count=paper_count,
        )
        for canonical, paper_count in results
    ]


@router.get(
    "/{canonical_document_id}",
    response_model=CanonicalDocumentResponse,
    summary="Lay chi tiet mot canonical document",
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
def get_canonical_document(
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
    return canonical


@router.get(
    "/by-paper/{paper_id}",
    response_model=CanonicalDocumentResponse,
    summary="Lay canonical document cua mot paper",
    description="""
Tien ich cho frontend: tu paper_id lay thang canonical document tuong ung
ma khong can biet canonical_document_id truoc.
""",
    responses={
        404: {
            "description": "Paper hoac canonical document khong ton tai",
        }
    },
)
def get_canonical_document_by_paper(
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

    canonical = (
        db.query(CanonicalDocument)
        .filter(CanonicalDocument.id == paper.canonical_document_id)
        .first()
    )
    if not canonical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical document not found.",
        )

    return canonical

@router.get(
    "/{canonical_document_id}/papers",
    response_model=list[PaperInCanonicalResponse],
    summary="Lay danh sach papers dang tham chieu toi canonical document",
    description="""
Tra ve danh sach PaperRecord co canonical_document_id = canonical_document_id.
Huu ich cho frontend khi can xem tat ca cac ban upload trung ve cung mot canonical.
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
def get_papers_of_canonical_document(
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

    papers = (
        db.query(PaperRecord)
        .filter(PaperRecord.canonical_document_id == canonical_document_id)
        .order_by(PaperRecord.created_at.asc())
        .all()
    )

    return papers