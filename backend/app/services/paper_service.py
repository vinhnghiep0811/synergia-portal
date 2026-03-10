import hashlib
import os
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_SIZE_BYTES
from app.models.paper_record import PaperRecord
from app.repositories.paper_repository import PaperRepository
from app.services.storage_service import StorageService


class PaperService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PaperRepository(db)
        self.storage = StorageService()

    async def upload_pdf(
        self,
        file: UploadFile,
        uploader_id: str | None = None,
    ) -> PaperRecord:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required.",
            )

        filename_lower = file.filename.lower()
        if not filename_lower.endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed.",
            )

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds max size of {MAX_UPLOAD_SIZE_BYTES} bytes.",
            )

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file signature.",
            )

        file_hash_sha256 = hashlib.sha256(content).hexdigest()
        paper_id = uuid4()
        ext = os.path.splitext(file.filename)[1] or ".pdf"
        object_name = f"papers/{paper_id}{ext}"

        storage_path = self.storage.upload_pdf_bytes(
            object_name=object_name,
            content=content,
            content_type=file.content_type or "application/pdf",
        )

        paper = PaperRecord(
            id=paper_id,
            uploader_id=uploader_id,
            original_filename=file.filename,
            storage_path=storage_path,
            mime_type=file.content_type or "application/pdf",
            file_size_bytes=len(content),
            file_hash_sha256=file_hash_sha256,
            upload_source="portal",
            status="pending",
        )

        return self.repo.create(paper)

    def list_papers(self, skip: int = 0, limit: int = 20):
        return self.repo.list(skip=skip, limit=limit)

    def get_paper_detail(self, paper_id):
        paper = self.repo.get_by_id(paper_id)
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found.",
            )
        return paper