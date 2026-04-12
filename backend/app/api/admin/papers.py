from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.models.paper_record import PaperRecord
from app.schemas.paper import (
    AdminPaperDetailResponse,
    AdminPaperListPaginatedResponse,
)

router = APIRouter()

@router.get("/papers", response_model=AdminPaperListPaginatedResponse)
def get_admin_papers(
    processing_status: Optional[str] = Query(None),
    processing_stage: Optional[str] = Query(None),
    publication_status: Optional[str] = Query(None),
    is_duplicate: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        db.query(PaperRecord)
        .options(selectinload(PaperRecord.canonical_document))
    )

    if processing_status:
        query = query.filter(PaperRecord.processing_status == processing_status)

    if processing_stage:
        query = query.filter(PaperRecord.processing_stage == processing_stage)

    if publication_status:
        query = query.filter(PaperRecord.publication_status == publication_status)

    if is_duplicate is not None:
        query = query.filter(PaperRecord.is_duplicate == is_duplicate)

    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                PaperRecord.original_filename.ilike(keyword),
                PaperRecord.detected_title.ilike(keyword),
            )
        )

    allowed_sort_fields = {
        "created_at": PaperRecord.created_at,
        "updated_at": PaperRecord.updated_at,
        "original_filename": PaperRecord.original_filename,
        "processing_status": PaperRecord.processing_status,
        "publication_status": PaperRecord.publication_status,
    }

    sort_column = allowed_sort_fields.get(sort_by, PaperRecord.created_at)

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()

    papers = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": papers,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.get("/papers/{paper_id}", response_model=AdminPaperDetailResponse)
def get_admin_paper_detail(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    paper = (
        db.query(PaperRecord)
        .options(selectinload(PaperRecord.canonical_document))
        .filter(PaperRecord.id == paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper