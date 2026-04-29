import logging

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def generate_embedding(canonical_id: str):
    db = SessionLocal()

    try:
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.canonical_document_id == canonical_id)
            .filter(DocumentChunk.is_retrievable == True)
            .filter(DocumentChunk.content.isnot(None))
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        chunks = [c for c in chunks if c.content and c.content.strip()]

        if not chunks:
            logger.info("[embedding] No valid chunks for canonical_id=%s", canonical_id)
            return

        logger.info(
            "[embedding] Start canonical_id=%s chunks=%s",
            canonical_id,
            len(chunks),
        )

        embedding_svc = EmbeddingService()

        texts = [c.content for c in chunks]
        embeddings = embedding_svc.generate_embeddings(texts, batch_size=32)

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: chunks={len(chunks)}, embeddings={len(embeddings)}"
            )

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        db.commit()

        logger.info(
            "[embedding] Done canonical_id=%s chunks=%s",
            canonical_id,
            len(chunks),
        )

    except Exception:
        db.rollback()
        logger.exception("[embedding] Failed canonical_id=%s", canonical_id)
        raise

    finally:
        db.close()