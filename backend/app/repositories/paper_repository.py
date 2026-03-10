from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.paper_record import PaperRecord


class PaperRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, paper: PaperRecord) -> PaperRecord:
        self.db.add(paper)
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def get_by_id(self, paper_id: UUID) -> Optional[PaperRecord]:
        return (
            self.db.query(PaperRecord)
            .filter(PaperRecord.id == paper_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 20) -> list[PaperRecord]:
        return (
            self.db.query(PaperRecord)
            .order_by(PaperRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )