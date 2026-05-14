from rq import Retry
from sqlalchemy.orm import Session

from app.core.queue import parse_queue, docling_queue, structure_queue, embedding_queue
from app.services.runtime_config_service import RuntimeConfigService


class QueueService:
    def __init__(self, db: Session | None = None):
        self.runtime_config = RuntimeConfigService.get(db)

    def _retry_policy(self) -> Retry | None:
        retry_limit = max(0, int(self.runtime_config.pipeline_retry_limit))
        if retry_limit <= 0:
            return None
        return Retry(max=retry_limit, interval=30)

    def _job_timeout_seconds(self, timeout_multiplier: int = 1, minimum_timeout: int = 60) -> int:
        base_timeout = max(10, int(self.runtime_config.pipeline_timeout_seconds))
        return max(minimum_timeout, base_timeout * max(1, timeout_multiplier))

    def _enqueue(
        self,
        queue,
        func_path: str,
        *args,
        timeout_multiplier: int = 1,
        minimum_timeout: int = 60,
    ):
        enqueue_kwargs = {
            "job_timeout": self._job_timeout_seconds(
                timeout_multiplier=timeout_multiplier,
                minimum_timeout=minimum_timeout,
            ),
        }
        retry_policy = self._retry_policy()
        if retry_policy is not None:
            enqueue_kwargs["retry"] = retry_policy
        return queue.enqueue(func_path, *args, **enqueue_kwargs)

    def enqueue_pdf_parse(self, paper_id: str):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.pdf_parse.pdf_parse",
            paper_id,
            timeout_multiplier=1,
            minimum_timeout=300,
        )
    
    def enqueue_docling(self, paper_id: str):
        return self._enqueue(
            docling_queue,
            "tasks.docling.extract_docling_text",
            paper_id,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_semantic_scholar(self, canonical_document_id: str):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.semantic_scholar.semantic_scholar_enrich",
            canonical_document_id,
            timeout_multiplier=1,
            minimum_timeout=300,
        )

    def enqueue_llm_extract(self, canonical_document_id: str):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.llm_extract.llm_extract",
            canonical_document_id,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_citation_graph_for_canonical(
        self,
        canonical_document_id: str,
        algorithm_version: str | None = None,
    ):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.citation_graph.score_citation_graph_for_canonical",
            canonical_document_id,
            algorithm_version,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_citation_graph_global(
        self,
        algorithm_version: str | None = None,
    ):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.citation_graph.score_citation_graph_global",
            algorithm_version,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_citation_graph_for_sources(
        self,
        source_canonical_ids: list[str],
        algorithm_version: str | None = None,
    ):
        return self._enqueue(
            parse_queue,
            "worker_app.tasks.citation_graph.score_citation_graph_for_sources",
            source_canonical_ids,
            algorithm_version,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_build_structure(self, canonical_id: str):
        return self._enqueue(
            structure_queue,
            "worker_app.tasks.build_structure.build_structure",
            canonical_id,
            timeout_multiplier=2,
            minimum_timeout=600,
        )

    def enqueue_embedding(self, canonical_id: str):
        return self._enqueue(
            embedding_queue,
            "worker_app.tasks.generate_embedding.generate_embedding",
            canonical_id,
            timeout_multiplier=4,
            minimum_timeout=1200,
        )
