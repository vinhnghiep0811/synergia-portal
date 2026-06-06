from app.core.database import SessionLocal
from app.models.document_section import DocumentSection
from app.models.document_chunk import DocumentChunk
from app.services.document_structure_service import DocumentStructureService
from app.services.storage_service import StorageService
from app.models.paper_record import PaperRecord

def build_structure(canonical_id: str):
    db = SessionLocal()

    try:
        paper = db.query(PaperRecord)\
            .filter(PaperRecord.canonical_document_id == canonical_id)\
            .first()

        if not paper or not paper.docling_markdown_storage_path:
            return

        storage = StorageService()
        markdown_bytes = storage.download_by_storage_path(
            paper.docling_markdown_storage_path
        )
        markdown = markdown_bytes.decode("utf-8").replace("\x00", "")

        structure_service = DocumentStructureService()

        # clear old
        db.query(DocumentChunk).filter(
            DocumentChunk.canonical_document_id == canonical_id
        ).delete()

        db.query(DocumentSection).filter(
            DocumentSection.canonical_document_id == canonical_id
        ).delete()

        # build sections
        sections = structure_service.parse_markdown_to_sections(
            canonical_document_id=canonical_id,
            markdown=markdown
        )

        db.add_all(sections)
        db.flush()

        # build chunks
        chunks = structure_service.build_chunks_from_sections(
            canonical_document_id=canonical_id,
            sections=sections
        )

        db.add_all(chunks)

        db.commit()

        # enqueue embedding
        from app.services.queue_service import QueueService
        QueueService(db).enqueue_embedding(canonical_id)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
