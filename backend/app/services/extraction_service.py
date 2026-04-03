# app/services/extraction_service.py

from sqlalchemy.orm import Session
from app.models.paper_record import PaperRecord
from app.models.extraction_run import ExtractionRun


class ExtractionQueryService:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_by_paper_id(self, paper_id):
        paper = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.id == paper_id)
            .first()
        )
        if not paper:
            return None

        if not paper.canonical_document_id:
            return None

        extraction = (
            self.db.query(ExtractionRun)
            .filter(
                ExtractionRun.canonical_document_id
                == paper.canonical_document_id
            )
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )

        return extraction