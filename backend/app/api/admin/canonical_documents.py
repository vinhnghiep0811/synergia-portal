from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_
from typing import Optional, List, Any
from uuid import UUID
import json

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.models.paper_record import PaperRecord
from app.models.canonical_document import CanonicalDocument
from app.schemas.canonical_document import (
    CanonicalDocumentDeleteResponse,
    CanonicalDocumentListItemResponse,
    CanonicalDocumentListPaginatedResponse,
    CanonicalDocumentResponse,
)
from app.services.delete_service import DeleteConflictError, DeleteService

router = APIRouter()

@router.get("/canonical-documents", response_model=CanonicalDocumentListPaginatedResponse)
def get_admin_canonical_documents(
    q: Optional[str] = Query(None),
    enrichment_status: Optional[str] = Query(None),
    match_status: Optional[str] = Query(None),
    canonical_type: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        db.query(
            CanonicalDocument,
            func.count(PaperRecord.id).label("paper_count"),
        )
        .outerjoin(PaperRecord, PaperRecord.canonical_document_id == CanonicalDocument.id)
        .group_by(CanonicalDocument.id)
    )

    if enrichment_status:
        query = query.filter(CanonicalDocument.enrichment_status == enrichment_status)

    if match_status:
        query = query.filter(CanonicalDocument.match_status == match_status)

    if canonical_type:
        query = query.filter(CanonicalDocument.canonical_type == canonical_type)

    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                CanonicalDocument.title.ilike(keyword),
                CanonicalDocument.title_candidate.ilike(keyword),
                CanonicalDocument.doi.ilike(keyword),
                CanonicalDocument.canonical_key.ilike(keyword),
            )
        )

    allowed_sort_fields = {
        "created_at": CanonicalDocument.created_at,
        "publication_year": CanonicalDocument.publication_year,
        "title": CanonicalDocument.title,
        "enrichment_status": CanonicalDocument.enrichment_status,
        "match_status": CanonicalDocument.match_status,
    }
    sort_column = allowed_sort_fields.get(sort_by, CanonicalDocument.created_at)

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()

    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for canonical, paper_count in rows:
        item = CanonicalDocumentListItemResponse.model_validate(
            {
                "id": canonical.id,
                "canonical_key": canonical.canonical_key,
                "canonical_type": canonical.canonical_type,
                "doi": canonical.doi,
                "title": canonical.title,
                "title_candidate": canonical.title_candidate,
                "publication_year": canonical.publication_year,
                "venue": canonical.venue,
                "enrichment_status": canonical.enrichment_status,
                "match_status": canonical.match_status,
                "metadata_source": canonical.metadata_source,
                "crossref_match_status": canonical.crossref_match_status,
                "crossref_match_confidence": canonical.crossref_match_confidence,
                "created_at": canonical.created_at,
                "paper_count": paper_count,
            }
        )
        items.append(item)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.get("/canonical-documents/export", response_model=List[Any])
def export_canonical_documents_metadata(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    canonical_docs = (
        db.query(CanonicalDocument)
        .options(selectinload(CanonicalDocument.latest_extraction_run))
        .all()
    )

    export_data = []
    for doc in canonical_docs:
        run = doc.latest_extraction_run
        
        # Format authors
        authors = []
        if isinstance(doc.authors_json, list):
            for a in doc.authors_json:
                if isinstance(a, dict):
                    authors.append(a.get("name", ""))
                else:
                    authors.append(str(a))
        elif isinstance(doc.authors_json, str):
            try:
                parsed_authors = json.loads(doc.authors_json)
                if isinstance(parsed_authors, list):
                    for a in parsed_authors:
                        if isinstance(a, dict):
                            authors.append(a.get("name", ""))
                        else:
                            authors.append(str(a))
            except Exception:
                authors = [doc.authors_json]

        # Extract LLM fields
        problem = None
        method = None
        contributions = []
        limitations = []
        evaluation_setup = None

        if run and run.status == "completed":
            problem = run.problem_statement
            method = run.main_method
            contributions = run.contributions or []
            limitations = run.limitations or []
            evaluation_setup = run.evaluation_setup

        export_data.append({
            "id": str(doc.id),
            "canonical_key": doc.canonical_key,
            "title": doc.title or doc.title_candidate,
            "abstract": doc.abstract,
            "year": doc.publication_year,
            "venue": doc.venue,
            "authors": authors,
            "doi": doc.doi,
            "problem": problem,
            "method": method,
            "contributions": contributions,
            "limitations": limitations,
            "evaluation_setup": evaluation_setup,
        })
    return export_data


@router.get("/canonical-documents/{canonical_id}", response_model=CanonicalDocumentResponse)
def get_admin_canonical_document_detail(
    canonical_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    canonical = (
        db.query(CanonicalDocument)
        .filter(CanonicalDocument.id == canonical_id)
        .first()
    )

    if not canonical:
        raise HTTPException(status_code=404, detail="Canonical document not found")

    return canonical


@router.delete(
    "/canonical-documents/{canonical_id}",
    response_model=CanonicalDocumentDeleteResponse,
    summary="Delete a canonical document",
    status_code=status.HTTP_200_OK,
)
def delete_admin_canonical_document(
    canonical_id: UUID,
    delete_papers: bool = Query(
        False,
        description=(
            "When true, delete all PaperRecord rows linked to this canonical "
            "document before deleting the canonical document."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = DeleteService(db)

    try:
        return service.delete_canonical_document(
            canonical_id,
            delete_papers=delete_papers,
            actor_user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DeleteConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
