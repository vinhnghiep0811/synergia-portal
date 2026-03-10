from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.paper import (
    PaperDetailResponse,
    PaperListItemResponse,
    PaperUploadResponse,
)
from app.services.paper_service import PaperService

router = APIRouter(prefix="/papers", tags=["papers"])


@router.post("/upload", response_model=PaperUploadResponse)
async def upload_paper(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    paper = await service.upload_pdf(file=file)
    return paper


@router.get("", response_model=list[PaperListItemResponse])
def list_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    return service.list_papers(skip=skip, limit=limit)


@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper_detail(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    return service.get_paper_detail(paper_id)