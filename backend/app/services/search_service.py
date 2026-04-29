import logging
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.models.canonical_document import CanonicalDocument
from app.services.embedding_service import EmbeddingService
from app.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384

SECTION_TYPE_WEIGHTS = {
    "abstract": 0.06,
    "introduction": 0.01,
    "background": 0.01,
    "related_work": -0.01,
    "method": 0.06,
    "evaluation": 0.03,
    "results": 0.03,
    "discussion": 0.01,
    "limitations": 0.03,
    "conclusion": -0.01,
    "references": -0.10,
    "appendix": -0.10,
    "declaration": -0.10,
    "other": 0.0,
}

EXCLUDED_SECTION_TYPES = {
    "references",
    "appendix",
    "declaration",
}

EXCLUDED_SECTION_KEYWORDS = [
    "references",
    "bibliography",
    "acknowledgement",
    "acknowledgment",
    "declaration",
    "appendix",
]

SOFT_EXCLUDED_SECTION_KEYWORDS = [
    "experiment",
    "qualitative result",
    "case study",
]


class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    def semantic_search(self, query: str, top_k: int = 5) -> list[SearchResultItem]:
        if not query or not query.strip():
            return []

        raw_query = query.strip()
        top_k = max(1, min(top_k, 20))

        logger.info("[search] query='%s' top_k=%s", raw_query, top_k)

        query_for_embedding = (
            f"Represent this sentence for searching relevant passages: {raw_query}"
        )
        query_vector = self.embedding_service.generate_embedding(query_for_embedding)

        if not query_vector or len(query_vector) != EMBEDDING_DIM:
            logger.warning("[search] Invalid query embedding.")
            return []

        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        candidate_limit = max(top_k * 10, 30)

        rows = (
            self.db.query(
                DocumentChunk,
                CanonicalDocument.title_candidate,
                distance.label("distance"),
            )
            .join(
                CanonicalDocument,
                DocumentChunk.canonical_document_id == CanonicalDocument.id,
            )
            .filter(DocumentChunk.embedding.isnot(None))
            .filter(DocumentChunk.is_retrievable == True)
            .filter(~DocumentChunk.section_type.in_(EXCLUDED_SECTION_TYPES))
            .order_by(distance)
            .limit(candidate_limit)
            .all()
        )

        if not rows:
            return []

        candidates: list[dict[str, Any]] = []

        for chunk, title_candidate, dist in rows:
            if chunk.embedding is None:
                continue

            if self._is_hard_excluded_section(chunk):
                continue

            similarity = 1.0 - float(dist if dist is not None else 1.0)
            section_boost = self._section_boost(chunk.section_type)
            section_penalty = self._section_penalty(chunk.section)
            query_boost = self._query_aware_boost(raw_query, chunk)

            final_relevance = similarity + section_boost + section_penalty + query_boost

            candidates.append(
                {
                    "chunk": chunk,
                    "title": title_candidate,
                    "similarity": similarity,
                    "relevance": final_relevance,
                    "embedding": chunk.embedding,
                }
            )

        selected = self._mmr_select(
            candidates=candidates,
            top_k=top_k,
            lambda_mult=0.65,
            duplicate_threshold=0.88,
        )

        return [
            SearchResultItem(
                chunk_id=item["chunk"].id,
                canonical_document_id=item["chunk"].canonical_document_id,
                title=item["title"],
                content=item["chunk"].content,
                similarity_score=round(item["relevance"], 4),
            )
            for item in selected
        ]

    def _section_boost(self, section_type: str | None) -> float:
        if not section_type:
            return 0.0

        return SECTION_TYPE_WEIGHTS.get(section_type, 0.0)

    def _section_penalty(self, section: str | None) -> float:
        section_lower = (section or "").lower()

        for keyword in SOFT_EXCLUDED_SECTION_KEYWORDS:
            if keyword in section_lower:
                return -0.06

        return 0.0

    def _is_hard_excluded_section(self, chunk: DocumentChunk) -> bool:
        section = (chunk.section or "").lower()
        section_type = (chunk.section_type or "").lower()

        if section_type in EXCLUDED_SECTION_TYPES:
            return True

        return any(keyword in section for keyword in EXCLUDED_SECTION_KEYWORDS)

    def _mmr_select(
        self,
        candidates: list[dict[str, Any]],
        top_k: int,
        lambda_mult: float = 0.65,
        duplicate_threshold: float = 0.88,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        selected: list[dict[str, Any]] = []
        remaining = candidates.copy()

        first = max(remaining, key=lambda x: x["relevance"])
        selected.append(first)
        remaining.remove(first)

        while remaining and len(selected) < top_k:
            best_item = None
            best_score = -float("inf")

            for item in remaining:
                max_sim_to_selected = max(
                    self._cosine_similarity(item["embedding"], s["embedding"])
                    for s in selected
                )

                # Bỏ chunk quá giống chunk đã chọn
                if max_sim_to_selected >= duplicate_threshold:
                    continue

                mmr_score = (
                    lambda_mult * item["relevance"]
                    - (1.0 - lambda_mult) * max_sim_to_selected
                )

                # Phạt nếu cùng section root
                if self._same_section_root(item["chunk"], selected):
                    mmr_score -= 0.08

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item

            # Nếu tất cả đều bị duplicate_threshold loại, nới điều kiện để vẫn trả đủ top_k
            if best_item is None:
                best_item = max(remaining, key=lambda x: x["relevance"])

            selected.append(best_item)
            remaining.remove(best_item)

        return selected

    def _same_section_root(
        self,
        item_chunk: DocumentChunk,
        selected_items: list[dict[str, Any]],
    ) -> bool:
        item_root = (item_chunk.section or "").split(">")[0].strip().lower()

        if not item_root:
            return False

        for selected in selected_items:
            selected_root = (
                selected["chunk"].section or ""
            ).split(">")[0].strip().lower()

            if item_root == selected_root:
                return True

        return False

    def _cosine_similarity(self, vec_a, vec_b) -> float:
        if vec_a is None or vec_b is None:
            return 0.0

        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)

        if a.size == 0 or b.size == 0:
            return 0.0

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def _query_aware_boost(self, query: str, chunk: DocumentChunk) -> float:
        q = query.lower()
        section_type = (chunk.section_type or "").lower()
        section = (chunk.section or "").lower()

        boost = 0.0

        process_terms = [
            "how", "work", "works", "workflow", "pipeline",
            "process", "break down", "decompose", "orchestrate",
            "step", "steps", "mechanism"
        ]

        evaluation_terms = [
            "evaluate", "evaluation", "experiment", "result",
            "performance", "metric", "benchmark", "accuracy",
            "precision", "recall", "f1"
        ]

        limitation_terms = [
            "limitation", "challenge", "risk", "problem",
            "weakness", "failure"
        ]

        summary_terms = [
            "summary", "overview", "what is", "main idea",
            "contribution", "abstract"
        ]

        if any(t in q for t in process_terms):
            if section_type == "method":
                boost += 0.08
            if section_type == "introduction":
                boost -= 0.02

        if any(t in q for t in evaluation_terms):
            if section_type in {"evaluation", "results"}:
                boost += 0.08

        if any(t in q for t in limitation_terms):
            if section_type in {"limitations", "discussion"}:
                boost += 0.08

        if any(t in q for t in summary_terms):
            if section_type in {"abstract", "introduction"}:
                boost += 0.06

        # ưu tiên subsection có tên khớp ý query, nhưng vẫn generic
        if "planning" in q and "planning" in section:
            boost += 0.06
        if "selection" in q and "selection" in section:
            boost += 0.06
        if "execution" in q and "execution" in section:
            boost += 0.06
        if "response" in q and "response" in section:
            boost += 0.06

        return boost