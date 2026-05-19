import logging
import re
from typing import Any

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, Text as SQLText

from app.models.document_chunk import DocumentChunk
from app.models.canonical_document import CanonicalDocument
from app.services.embedding_service import EmbeddingService
from app.services.runtime_config_service import RuntimeConfigService
from app.schemas.search import SearchResultItem
from app.models.paper_record import PaperRecord
logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384

SECTION_TYPE_WEIGHTS = {
    "abstract": 0.02,
    "introduction": 0.01,
    "background": 0.01,
    "related_work": -0.01,
    "method": 0.08,
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
    "qualitative result",
    "case study",
]


class SearchService:
    def __init__(self, db: Session):
        self.db = db
        runtime_config = RuntimeConfigService.get(db)
        self.embedding_service = EmbeddingService(model_name=runtime_config.embedding_model)

    def _has_published_paper_for_canonical(self, canonical_id_column):
        return (
            self.db.query(PaperRecord.id)
            .filter(
                PaperRecord.canonical_document_id == canonical_id_column,
                PaperRecord.publication_status == "published",
            )
            .exists()
        )

    def semantic_search(self, query: str, top_k: int = 5, canonical_document_id: str | None = None,) -> list[SearchResultItem]:
        if not query or not query.strip():
            return []

        raw_query = query.strip()
        top_k = max(1, min(top_k, 20))
        query_type = self._detect_query_type(raw_query)

        logger.info(
            "[search] query='%s' top_k=%s query_type=%s",
            raw_query,
            top_k,
            query_type,
        )

        query_for_embedding = (
            f"Represent this sentence for searching relevant passages: {raw_query}"
        )
        query_vector = self.embedding_service.generate_embedding(query_for_embedding)

        if not query_vector or len(query_vector) != EMBEDDING_DIM:
            logger.warning("[search] Invalid query embedding.")
            return []

        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        candidate_limit = max(top_k * 12, 40)

        rows_query = (
            self.db.query(
                DocumentChunk,
                CanonicalDocument.title,
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
            .filter(self._has_published_paper_for_canonical(DocumentChunk.canonical_document_id))
        )

        if canonical_document_id:
            rows_query = rows_query.filter(DocumentChunk.canonical_document_id == canonical_document_id)

        rows = rows_query.order_by(distance).limit(candidate_limit).all()

        if not rows:
            return []

        candidates: list[dict[str, Any]] = []

        for chunk, title, title_candidate, dist in rows:
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
                    "title": title or title_candidate,
                    "similarity": similarity,
                    "relevance": final_relevance,
                    "embedding": chunk.embedding,
                }
            )

        if not candidates:
            return []

        selected = self._mmr_select(
            candidates=candidates,
            top_k=top_k,
            lambda_mult=0.65,
            duplicate_threshold=0.88,
            query_type=query_type,
        )

        if query_type == "comparison":
            selected = self._ensure_multi_document(
                selected=selected,
                candidates=candidates,
                top_k=top_k,
            )

        return [
            SearchResultItem(
                chunk_id=item["chunk"].id,
                canonical_document_id=item["chunk"].canonical_document_id,
                title=item["title"],
                content=self._semantic_evidence_snippet(raw_query, item["chunk"].content),
                similarity_score=round(item["relevance"], 4),
                source="semantic",
                section=item["chunk"].section,
                section_type=item["chunk"].section_type,
                page_from=item["chunk"].page_from,
                page_to=item["chunk"].page_to,
            )
            for item in selected[:top_k]
        ]

    def _detect_query_type(self, query: str) -> str:
        q = query.lower()

        if any(w in q for w in ["compare", "difference", "differ", "vs", "versus"]):
            return "comparison"

        if any(w in q for w in ["how", "process", "workflow", "pipeline", "mechanism"]):
            return "process"

        return "general"

    def _section_boost(self, section_type: str | None) -> float:
        if not section_type:
            return 0.0

        return SECTION_TYPE_WEIGHTS.get(section_type.lower(), 0.0)

    def _section_penalty(self, section: str | None) -> float:
        section_lower = (section or "").lower()

        for keyword in SOFT_EXCLUDED_SECTION_KEYWORDS:
            if keyword in section_lower:
                return -0.04

        return 0.0

    def _query_aware_boost(self, query: str, chunk: DocumentChunk) -> float:
        q = query.lower()
        section_type = (chunk.section_type or "").lower()
        section = (chunk.section or "").lower()
        full_path = (getattr(chunk, "section_full_path", "") or "").lower()

        boost = 0.0

        process_terms = [
            "how", "work", "works", "workflow", "pipeline",
            "process", "break down", "decompose", "orchestrate",
            "step", "steps", "mechanism", "handle", "handling",
        ]

        evaluation_terms = [
            "evaluate", "evaluation", "experiment", "result",
            "performance", "metric", "benchmark", "accuracy",
            "precision", "recall", "f1",
        ]

        limitation_terms = [
            "limitation", "challenge", "risk", "problem",
            "weakness", "failure",
        ]

        summary_terms = [
            "summary", "overview", "what is", "main idea",
            "contribution", "abstract",
        ]

        if any(t in q for t in process_terms):
            if section_type == "method":
                boost += 0.10
            if section_type == "introduction":
                boost -= 0.03

        if any(t in q for t in evaluation_terms):
            if section_type in {"evaluation", "results"}:
                boost += 0.08

        if any(t in q for t in limitation_terms):
            if section_type in {"limitations", "discussion"}:
                boost += 0.08

        if any(t in q for t in summary_terms):
            if section_type in {"abstract", "introduction"}:
                boost += 0.06

        # Generic subsection matching
        searchable_section = f"{section} {full_path}"

        keyword_pairs = [
            ("planning", "planning"),
            ("plan", "planning"),
            ("selection", "selection"),
            ("select", "selection"),
            ("execution", "execution"),
            ("execute", "execution"),
            ("response", "response"),
            ("memory", "memory"),
            ("reasoning", "reasoning"),
            ("perception", "perception"),
            ("interaction", "interaction"),
            ("governance", "governance"),
            ("risk", "risk"),
            ("safeguard", "safeguard"),
            ("autonomy", "autonomy"),
        ]

        for query_term, section_term in keyword_pairs:
            if query_term in q and section_term in searchable_section:
                boost += 0.06

        return boost

    def _is_hard_excluded_section(self, chunk: DocumentChunk) -> bool:
        section = (chunk.section or "").lower()
        section_type = (chunk.section_type or "").lower()
        full_path = (getattr(chunk, "section_full_path", "") or "").lower()

        if section_type in EXCLUDED_SECTION_TYPES:
            return True

        target = f"{section} {full_path}"

        return any(keyword in target for keyword in EXCLUDED_SECTION_KEYWORDS)

    def _mmr_select(
        self,
        candidates: list[dict[str, Any]],
        top_k: int,
        lambda_mult: float = 0.65,
        duplicate_threshold: float = 0.88,
        query_type: str = "general",
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

                if max_sim_to_selected >= duplicate_threshold:
                    continue

                mmr_score = (
                    lambda_mult * item["relevance"]
                    - (1.0 - lambda_mult) * max_sim_to_selected
                )

                if self._same_section_root(item["chunk"], selected):
                    mmr_score -= 0.08

                if query_type == "comparison":
                    if self._is_new_document(item, selected):
                        mmr_score += 0.08

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item

            if best_item is None:
                best_item = max(remaining, key=lambda x: x["relevance"])

            selected.append(best_item)
            remaining.remove(best_item)

        return selected

    def _ensure_multi_document(
        self,
        selected: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not selected:
            return []

        selected_doc_ids = {
            item["chunk"].canonical_document_id
            for item in selected
        }

        candidate_doc_ids = {
            item["chunk"].canonical_document_id
            for item in candidates
        }

        if len(candidate_doc_ids) <= 1:
            return selected

        if len(selected_doc_ids) >= min(2, len(candidate_doc_ids)):
            return selected

        missing_doc_items = []

        for item in sorted(candidates, key=lambda x: x["relevance"], reverse=True):
            doc_id = item["chunk"].canonical_document_id

            if doc_id not in selected_doc_ids:
                missing_doc_items.append(item)
                selected_doc_ids.add(doc_id)

            if len(selected_doc_ids) >= min(2, len(candidate_doc_ids)):
                break

        if not missing_doc_items:
            return selected

        final = selected.copy()

        for item in missing_doc_items:
            already_exists = any(
                x["chunk"].id == item["chunk"].id
                for x in final
            )

            if not already_exists:
                final.append(item)

        final.sort(key=lambda x: x["relevance"], reverse=True)

        return final[:top_k]

    def _is_new_document(
        self,
        item: dict[str, Any],
        selected_items: list[dict[str, Any]],
    ) -> bool:
        item_doc_id = item["chunk"].canonical_document_id

        return all(
            selected["chunk"].canonical_document_id != item_doc_id
            for selected in selected_items
        )

    def _same_section_root(
        self,
        item_chunk: DocumentChunk,
        selected_items: list[dict[str, Any]],
    ) -> bool:
        item_root = self._section_root(item_chunk)

        if not item_root:
            return False

        for selected in selected_items:
            selected_root = self._section_root(selected["chunk"])

            if item_root == selected_root:
                return True

        return False

    def _section_root(self, chunk: DocumentChunk) -> str:
        full_path = getattr(chunk, "section_full_path", None)

        if full_path:
            return full_path.split(">")[0].strip().lower()

        return (chunk.section or "").split(">")[0].strip().lower()

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

    @staticmethod
    def _search_tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(token) > 2
        }

    def _semantic_evidence_snippet(self, query: str, content: str | None, window: int = 520) -> str:
        if not content:
            return ""

        content_clean = " ".join(content.split())
        if len(content_clean) <= window:
            return content_clean

        query_tokens = self._search_tokens(query)
        if not query_tokens:
            return content_clean[:window].strip() + "..."

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", content_clean)
            if sentence.strip()
        ]

        best_sentence = ""
        best_score = 0.0
        for sentence in sentences:
            sentence_tokens = self._search_tokens(sentence)
            if not sentence_tokens:
                continue

            overlap = len(query_tokens & sentence_tokens)
            coverage = overlap / max(len(query_tokens), 1)
            score = coverage + min(overlap * 0.08, 0.4)
            if score > best_score:
                best_score = score
                best_sentence = sentence

        if not best_sentence:
            return content_clean[:window].strip() + "..."

        index = content_clean.find(best_sentence)
        if index < 0:
            snippet = best_sentence[:window].strip()
            return snippet + ("..." if len(best_sentence) > window else "")

        start = max(0, index - window // 4)
        end = min(len(content_clean), index + len(best_sentence) + window // 4)
        snippet = content_clean[start:end].strip()
        if len(snippet) > window:
            snippet = snippet[:window].strip()

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content_clean) else ""
        return f"{prefix}{snippet}{suffix}"
    
    def keyword_search(self, query: str, limit: int = 20) -> list[SearchResultItem]:
        if not query or not query.strip():
            return []

        raw_query = query.strip()
        q_lower = raw_query.lower()
        pattern = f"%{raw_query}%"
        limit = max(1, min(limit, 50))

        results: list[SearchResultItem] = []
        seen: set[tuple[str, str]] = set()

        # 1) Search metadata: filename, detected title, DOI, canonical title, abstract, venue, authors
        metadata_rows = (
            self.db.query(PaperRecord, CanonicalDocument)
            .outerjoin(
                CanonicalDocument,
                PaperRecord.canonical_document_id == CanonicalDocument.id,
            )
            .filter(PaperRecord.publication_status == "published")
            .filter(
                or_(
                    PaperRecord.original_filename.ilike(pattern),
                    PaperRecord.detected_title.ilike(pattern),
                    PaperRecord.detected_doi.ilike(pattern),
                    PaperRecord.detected_fingerprint.ilike(pattern),
                    CanonicalDocument.title.ilike(pattern),
                    CanonicalDocument.title_candidate.ilike(pattern),
                    CanonicalDocument.normalized_title.ilike(pattern),
                    CanonicalDocument.abstract.ilike(pattern),
                    CanonicalDocument.venue.ilike(pattern),
                    CanonicalDocument.doi.ilike(pattern),
                    cast(CanonicalDocument.authors_json, SQLText).ilike(pattern),
                )
            )
            .order_by(PaperRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        for paper, canonical in metadata_rows:
            title = (
                getattr(canonical, "title", None)
                or getattr(canonical, "title_candidate", None)
                or paper.detected_title
                or paper.original_filename
            )

            content_parts = [
                f"Metadata match",
                f"Filename: {paper.original_filename}",
            ]

            if paper.detected_title:
                content_parts.append(f"Detected title: {paper.detected_title}")
            if paper.detected_doi:
                content_parts.append(f"DOI: {paper.detected_doi}")
            if canonical:
                if canonical.title:
                    content_parts.append(f"Title: {canonical.title}")
                if canonical.venue:
                    content_parts.append(f"Venue: {canonical.venue}")
                if canonical.publication_year:
                    content_parts.append(f"Year: {canonical.publication_year}")
                if canonical.abstract:
                    content_parts.append(
                        f"Abstract: {self._keyword_snippet(canonical.abstract, raw_query)}"
                    )

            score = self._keyword_score(
                q_lower=q_lower,
                title=title,
                filename=paper.original_filename,
                doi=paper.detected_doi or (canonical.doi if canonical else None),
                content="\n".join(content_parts),
            )

            key = ("metadata", str(paper.id))
            if key not in seen:
                seen.add(key)
                results.append(
                    SearchResultItem(
                        chunk_id=None,
                        canonical_document_id=paper.canonical_document_id,
                        paper_id=paper.id,
                        title=title,
                        content="\n".join(content_parts),
                        similarity_score=score,
                        source="metadata",
                    )
                )

        # 2) Search full text chunks
        remaining = max(limit - len(results), 0)
        if remaining > 0:
            chunk_rows = (
                self.db.query(DocumentChunk, CanonicalDocument)
                .join(
                    CanonicalDocument,
                    DocumentChunk.canonical_document_id == CanonicalDocument.id,
                )
                .filter(DocumentChunk.is_retrievable == True)
                .filter(self._has_published_paper_for_canonical(DocumentChunk.canonical_document_id))
                .filter(DocumentChunk.content.ilike(pattern))
                .order_by(DocumentChunk.created_at.desc())
                .limit(remaining * 3)
                .all()
            )

            for chunk, canonical in chunk_rows:
                snippet = self._keyword_snippet(chunk.content, raw_query)
                title = canonical.title or canonical.title_candidate

                key = ("chunk", str(chunk.id))
                if key in seen:
                    continue

                seen.add(key)
                results.append(
                    SearchResultItem(
                        chunk_id=chunk.id,
                        canonical_document_id=chunk.canonical_document_id,
                        paper_id=None,
                        title=title,
                        content=f"{chunk.section or 'Content match'}\n{snippet}",
                        similarity_score=self._chunk_keyword_score(
                            query=raw_query,
                            title=title,
                            section=chunk.section,
                            content=chunk.content,
                        ),
                        source="chunk",
                        section=chunk.section,
                        section_type=chunk.section_type,
                        page_from=chunk.page_from,
                        page_to=chunk.page_to,
                    )
                )

                if len(results) >= limit:
                    break

        results.sort(key=lambda item: item.similarity_score, reverse=True)
        deduped = []
        seen_docs = set()

        for item in results:
            doc_key = str(item.canonical_document_id or item.paper_id or item.chunk_id)

            if doc_key in seen_docs:
                continue

            seen_docs.add(doc_key)
            deduped.append(item)

            if len(deduped) >= limit:
                break

        return deduped

    def _keyword_snippet(self, content: str | None, query: str, window: int = 260) -> str:
        if not content:
            return ""

        content_clean = " ".join(content.split())
        content_lower = content_clean.lower()
        query_lower = query.lower()

        index = content_lower.find(query_lower)
        if index < 0:
            return content_clean[:window] + ("..." if len(content_clean) > window else "")

        start = max(0, index - window // 2)
        end = min(len(content_clean), index + len(query) + window // 2)

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content_clean) else ""

        return prefix + content_clean[start:end] + suffix

    def _keyword_score(
        self,
        q_lower: str,
        title: str | None,
        filename: str | None,
        doi: str | None,
        content: str | None,
    ) -> float:
        title_lower = (title or "").lower()
        filename_lower = (filename or "").lower()
        doi_lower = (doi or "").lower()
        content_lower = (content or "").lower()

        if q_lower in title_lower:
            return 1.0
        if q_lower in doi_lower:
            return 0.95
        if q_lower in filename_lower:
            return 0.9
        if q_lower in content_lower:
            return 0.75
        return 0.5
    
    def _chunk_keyword_score(
        self,
        query: str,
        title: str | None,
        section: str | None,
        content: str | None,
    ) -> float:
        query = query.strip().lower()
        title_lower = (title or "").lower()
        section_lower = (section or "").lower()
        content_lower = (content or "").lower()

        if not query or not content_lower:
            return 0.0

        terms = [term for term in query.split() if term]
        exact_count = content_lower.count(query)

        term_hits = sum(1 for term in terms if term in content_lower)
        term_coverage = term_hits / max(len(terms), 1)

        score = 0.4

        if query in title_lower:
            score += 0.35

        if query in section_lower:
            score += 0.15

        if exact_count > 0:
            score += 0.25

        score += min(exact_count * 0.03, 0.15)
        score += term_coverage * 0.2

        return round(min(score, 1.0), 4)
