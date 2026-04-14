from app.core.queue import parse_queue, docling_queue


class QueueService:
    def enqueue_pdf_parse(self, paper_id: str):
        return parse_queue.enqueue(
            "worker_app.tasks.pdf_parse.pdf_parse",
            paper_id
        )
    
    def enqueue_docling(self, paper_id: str):
        return docling_queue.enqueue(
            "tasks.docling.extract_docling_text",
            paper_id
        )

    def enqueue_llm_extract(self, canonical_document_id: str):
        return parse_queue.enqueue(
            "worker_app.tasks.llm_extract.llm_extract",
            canonical_document_id
        )