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
            paper_id,
            job_timeout=600,
        )

    def enqueue_llm_extract(self, canonical_document_id: str):
        return parse_queue.enqueue(
            "worker_app.tasks.llm_extract.llm_extract",
            canonical_document_id
        )

    def enqueue_citation_graph_for_canonical(
        self,
        canonical_document_id: str,
        algorithm_version: str | None = None,
    ):
        return parse_queue.enqueue(
            "worker_app.tasks.citation_graph.score_citation_graph_for_canonical",
            canonical_document_id,
            algorithm_version,
        )

    def enqueue_citation_graph_global(
        self,
        algorithm_version: str | None = None,
    ):
        return parse_queue.enqueue(
            "worker_app.tasks.citation_graph.score_citation_graph_global",
            algorithm_version,
        )

    def enqueue_citation_graph_for_sources(
        self,
        source_canonical_ids: list[str],
        algorithm_version: str | None = None,
    ):
        return parse_queue.enqueue(
            "worker_app.tasks.citation_graph.score_citation_graph_for_sources",
            source_canonical_ids,
            algorithm_version,
        )