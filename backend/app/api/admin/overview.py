from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import require_admin
from app.models.paper_record import PaperRecord
from app.models.user import User

router = APIRouter()


@router.get("/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    total_papers = db.query(PaperRecord).count()

    processing_rows = (
        db.query(PaperRecord.processing_status, func.count(PaperRecord.id))
        .group_by(PaperRecord.processing_status)
        .all()
    )

    publication_rows = (
        db.query(PaperRecord.publication_status, func.count(PaperRecord.id))
        .group_by(PaperRecord.publication_status)
        .all()
    )

    stage_rows = (
        db.query(PaperRecord.processing_stage, func.count(PaperRecord.id))
        .group_by(PaperRecord.processing_stage)
        .all()
    )

    duplicate_count = (
        db.query(PaperRecord)
        .filter(PaperRecord.is_duplicate.is_(True))
        .count()
    )

    return {
        "total_papers": total_papers,
        "processing_status": {
            (status if status is not None else "unknown"): count
            for status, count in processing_rows
        },
        "processing_stage": {
            (stage if stage is not None else "unknown"): count
            for stage, count in stage_rows
        },
        "publication_status": {
            (status if status is not None else "unknown"): count
            for status, count in publication_rows
        },
        "duplicate_count": duplicate_count,
        "current_admin": {
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
        },
    }