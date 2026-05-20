import logging
import json
import re
from typing import Any

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, Text as SQLText

from app.models.document_chunk import DocumentChunk
from app.models.canonical_document import CanonicalDocument
from app.services.embedding_service import EmbeddingService
from app.services.runtime_config_service import RuntimeConfigService
from app.services.storage_service import StorageService
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

SEARCH_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "onto",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "using",
    "use",
    "used",
    "system",
    "systems",
    "paper",
    "study",
    "model",
    "models",
    "approach",
    "approaches",
}

TECHNICAL_METHOD_TERMS = [
    "optimization",
    "optimisation",
    "optimize",
    "optimise",
    "optimizer",
    "training",
    "train",
    "learning rate",
    "regularization",
    "regularisation",
    "dropout",
    "label smoothing",
    "beam search",
    "decoding",
    "generation",
    "inference",
    "architecture",
    "technique",
    "techniques",
    "hyperparameter",
    "hyperparameters",
    "batching",
    "sequence-to-sequence",
    "sequence to sequence",
]

TECHNICAL_METHOD_SECTION_TERMS = [
    "training",
    "optimization",
    "optimisation",
    "generation",
    "decoding",
    "inference",
    "implementation",
    "architecture",
    "training data",
    "training technique",
    "batching",
    "hyperparameter",
    "model",
    "method",
    "approach",
]

TECHNICAL_METHOD_CONTENT_TERMS = [
    "adam",
    "optimizer",
    "learning rate",
    "warmup",
    "label smoothing",
    "dropout",
    "adadelta",
    "rmsprop",
    "sgd",
    "regularization",
    "regularisation",
    "beam search",
    "byte-pair",
    "bpe",
    "batch",
    "batching",
    "gradient",
    "gpu",
    "checkpoint",
    "epoch",
    "schedule",
    "decoding",
    "optimization",
    "optimisation",
    "technique",
]

TECHNICAL_METHOD_WEAK_SECTION_TYPES = {
    "abstract",
    "introduction",
    "background",
    "related_work",
}

TECHNICAL_METHOD_SECONDARY_SECTION_TYPES = {
    "evaluation",
    "results",
    "discussion",
    "conclusion",
}

OPTIMIZATION_EVIDENCE_TERMS = [
    "optimization",
    "optimisation",
    "optimizer",
    "adam",
    "adadelta",
    "rmsprop",
    "sgd",
    "learning rate",
    "warmup",
    "schedule",
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
        candidate_limit = min(300, max(top_k * 30, 120))

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
        lexical_rows = self._semantic_lexical_candidate_rows(
            base_query=rows_query,
            query=raw_query,
            query_type=query_type,
            distance=distance,
            candidate_limit=candidate_limit,
        )

        if lexical_rows:
            rows_by_chunk_id = {
                str(row[0].id): row
                for row in rows
            }
            for row in lexical_rows:
                rows_by_chunk_id.setdefault(str(row[0].id), row)
            rows = list(rows_by_chunk_id.values())

        if not rows:
            return []

        candidates: list[dict[str, Any]] = []

        for chunk, title, title_candidate, dist in rows:
            if chunk.embedding is None:
                continue

            if self._is_hard_excluded_section(chunk):
                continue

            resolved_title = title or title_candidate
            similarity = 1.0 - float(dist if dist is not None else 1.0)

            section_boost = self._section_boost(chunk.section_type)
            section_penalty = self._section_penalty(chunk.section)
            query_boost = self._query_aware_boost(raw_query, chunk)
            lexical_boost = self._lexical_relevance_boost(raw_query, chunk)
            query_coverage = self._query_coverage_score(raw_query, chunk, resolved_title)
            aspect_coverage = self._technical_aspect_coverage(raw_query, chunk, resolved_title)
            phrase_score = self._phrase_match_score(raw_query, chunk, resolved_title)

            final_relevance = self._combined_relevance_score(
                query_type=query_type,
                similarity=similarity,
                section_boost=section_boost,
                section_penalty=section_penalty,
                query_boost=query_boost,
                lexical_boost=lexical_boost,
                query_coverage=query_coverage,
                aspect_coverage=aspect_coverage,
                phrase_score=phrase_score,
            )

            candidates.append(
                {
                    "chunk": chunk,
                    "title": resolved_title,
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
            lambda_mult=0.82 if query_type == "technical_method" else 0.65,
            duplicate_threshold=0.94 if query_type == "technical_method" else 0.88,
            query_type=query_type,
        )

        if query_type == "comparison":
            selected = self._ensure_multi_document(
                selected=selected,
                candidates=candidates,
                top_k=top_k,
            )

        selected.sort(key=lambda item: item["relevance"], reverse=True)

        page_cache: dict[str, list[dict]] = {}
        results: list[SearchResultItem] = []
        for item in selected[:top_k]:
            chunk = item["chunk"]
            evidence_snippet = self._semantic_evidence_snippet(raw_query, chunk.content)
            page_from, page_to = self._resolve_result_pages(
                chunk,
                evidence_snippet,
                page_cache,
            )
            results.append(
                SearchResultItem(
                chunk_id=item["chunk"].id,
                canonical_document_id=item["chunk"].canonical_document_id,
                title=item["title"],
                content=evidence_snippet,
                similarity_score=round(item["relevance"], 4),
                source="semantic",
                section=chunk.section,
                section_type=chunk.section_type,
                page_from=page_from,
                page_to=page_to,
                )
            )

        return results

    def _detect_query_type(self, query: str) -> str:
        q = query.lower()

        if any(w in q for w in ["compare", "difference", "differ", "vs", "versus"]):
            return "comparison"

        if any(term in q for term in TECHNICAL_METHOD_TERMS):
            return "technical_method"

        if any(w in q for w in ["how", "process", "workflow", "pipeline", "mechanism"]):
            return "process"

        return "general"

    def _semantic_lexical_candidate_rows(
        self,
        base_query,
        query: str,
        query_type: str,
        distance,
        candidate_limit: int,
    ) -> list[Any]:
        terms = self._semantic_lexical_terms(query, query_type)
        if not terms:
            return []

        filters = []
        for term in terms:
            pattern = self._contains_pattern(term)
            filters.extend(
                [
                    DocumentChunk.content.ilike(pattern, escape="\\"),
                    DocumentChunk.section.ilike(pattern, escape="\\"),
                    DocumentChunk.section_full_path.ilike(pattern, escape="\\"),
                ]
            )

        return (
            base_query
            .filter(or_(*filters))
            .order_by(distance)
            .limit(candidate_limit)
            .all()
        )

    def _semantic_lexical_terms(self, query: str, query_type: str) -> list[str]:
        q = (query or "").lower()
        terms: set[str] = set()

        if query_type == "technical_method":
            if any(term in q for term in ["optimization", "optimisation", "optimize", "optimise", "technique"]):
                terms.update(OPTIMIZATION_EVIDENCE_TERMS)
                terms.update(
                    {
                        "training",
                        "training technique",
                        "batching",
                        "dropout",
                        "label smoothing",
                    }
                )

            if "sequence" in q or "translation" in q or "decoding" in q or "generation" in q:
                terms.update(
                    {
                        "beam search",
                        "generation",
                        "decoding",
                        "encoder",
                        "decoder",
                    }
                )

            terms.update(
                term
                for term in TECHNICAL_METHOD_TERMS
                if term in q
            )
        else:
            query_tokens = self._search_tokens(query)
            if len(query_tokens) >= 3:
                terms.update(
                    token
                    for token in query_tokens
                    if len(token) >= 6
                )

        return sorted(
            terms,
            key=lambda term: (
                0 if term in OPTIMIZATION_EVIDENCE_TERMS else 1,
                0 if " " in term else 1,
                -len(term),
                term,
            ),
        )[:18]

    @staticmethod
    def _contains_pattern(value: str) -> str:
        escaped = (
            (value or "")
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"%{escaped}%"

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

    def _combined_relevance_score(
        self,
        query_type: str,
        similarity: float,
        section_boost: float,
        section_penalty: float,
        query_boost: float,
        lexical_boost: float,
        query_coverage: float = 0.0,
        aspect_coverage: float = 1.0,
        phrase_score: float = 0.0,
    ) -> float:
        if query_type == "technical_method":
            base_score = (
                similarity * 0.64
                + query_coverage * 0.16
                + aspect_coverage * 0.08
                + phrase_score * 0.04
            )
            positive_cap = 0.18
            negative_floor = -0.24
        elif query_type == "comparison":
            base_score = similarity * 0.82 + query_coverage * 0.10 + phrase_score * 0.03
            positive_cap = 0.18
            negative_floor = -0.18
        else:
            base_score = similarity * 0.84 + query_coverage * 0.08 + phrase_score * 0.03
            positive_cap = 0.20
            negative_floor = -0.20

        adjustments = section_boost + section_penalty + query_boost + lexical_boost
        adjustments = min(max(adjustments, negative_floor), positive_cap)
        score = base_score + adjustments

        if query_type == "technical_method":
            if query_coverage < 0.35:
                score -= 0.08
            if aspect_coverage < 0.50:
                score -= 0.07
            if aspect_coverage < 0.34:
                score -= 0.05

        return self._clip_score(score)

    def _query_aware_boost(self, query: str, chunk: DocumentChunk) -> float:
        q = query.lower()
        section_type = (chunk.section_type or "").lower()
        section = (chunk.section or "").lower()
        full_path = (getattr(chunk, "section_full_path", "") or "").lower()
        content = (chunk.content or "").lower()

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

        if any(t in q for t in TECHNICAL_METHOD_TERMS):
            technical_signal = self._technical_method_signal_score(query, chunk)
            boost += min(technical_signal * 0.22, 0.22)

            if section_type == "method":
                boost += 0.04

            if section_type in TECHNICAL_METHOD_WEAK_SECTION_TYPES:
                if technical_signal < 0.30:
                    boost -= 0.16
                elif technical_signal < 0.50:
                    boost -= 0.08

            if section_type in TECHNICAL_METHOD_SECONDARY_SECTION_TYPES and technical_signal < 0.30:
                boost -= 0.08

            if "optimization" in q or "optimisation" in q:
                has_optimization_evidence = any(
                    term in content or term in section or term in full_path
                    for term in OPTIMIZATION_EVIDENCE_TERMS
                )
                if not has_optimization_evidence and section_type in TECHNICAL_METHOD_WEAK_SECTION_TYPES:
                    boost -= 0.06

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

    def _technical_method_signal_score(self, query: str, chunk: DocumentChunk) -> float:
        q = (query or "").lower()
        section_type = (chunk.section_type or "").lower()
        section = (chunk.section or "").lower()
        full_path = (getattr(chunk, "section_full_path", "") or "").lower()
        content = (chunk.content or "").lower()
        section_text = f"{section} {full_path}"
        searchable = f"{section_text} {content}"
        normalized_section_text = self._normalize_search_text(section_text)
        normalized_content = self._normalize_search_text(content)
        normalized_searchable = self._normalize_search_text(searchable)

        score = 0.0

        if section_type == "method":
            score += 0.25

        if any(self._normalized_term_in_text(term, normalized_section_text) for term in TECHNICAL_METHOD_SECTION_TERMS):
            score += 0.30

        content_hits = sum(
            1
            for term in TECHNICAL_METHOD_CONTENT_TERMS
            if self._normalized_term_in_text(term, normalized_content)
        )
        score += min(content_hits * 0.07, 0.35)

        query_tokens = self._search_tokens(query)
        searchable_tokens = self._search_tokens(searchable)
        if query_tokens and searchable_tokens:
            coverage = len(query_tokens & searchable_tokens) / max(len(query_tokens), 1)
            score += min(coverage * 0.20, 0.20)

        if "optimization" in q or "optimisation" in q:
            if any(self._normalized_term_in_text(term, normalized_searchable) for term in OPTIMIZATION_EVIDENCE_TERMS):
                score += 0.18
            else:
                score -= 0.08

        if "sequence" in q or "translation" in q:
            if any(self._normalized_term_in_text(term, normalized_searchable) for term in ["beam search", "generation", "decoding", "encoder", "decoder"]):
                score += 0.08

        if any(self._normalized_term_in_text(phrase, normalized_searchable) for phrase in ["optimization technique", "training technique"]):
            score += 0.12

        return self._clip_score(score)

    def _query_coverage_score(
        self,
        query: str,
        chunk: DocumentChunk,
        title: str | None = None,
    ) -> float:
        query_tokens = self._search_tokens(query)
        if not query_tokens:
            return 0.0

        searchable_tokens = self._search_tokens(self._searchable_text(chunk, title))
        if not searchable_tokens:
            return 0.0

        exact_hits = len(query_tokens & searchable_tokens)
        coverage = exact_hits / max(len(query_tokens), 1)
        phrase_score = self._phrase_match_score(query, chunk, title)

        return self._clip_score(coverage * 0.85 + phrase_score * 0.15)

    def _technical_aspect_coverage(
        self,
        query: str,
        chunk: DocumentChunk,
        title: str | None = None,
    ) -> float:
        q = self._normalize_search_text(query)
        searchable = self._normalize_search_text(self._searchable_text(chunk, title))
        aspects: list[list[str]] = []

        if any(term in q for term in ["optimization", "optimisation", "optimize", "optimise", "technique"]):
            aspects.append(
                [
                    "optimization",
                    "optimisation",
                    "optimizer",
                    "technique",
                    "adam",
                    "adadelta",
                    "rmsprop",
                    "sgd",
                    "learning rate",
                    "warmup",
                    "schedule",
                ]
            )

        if "sequence to sequence" in q or "seq2seq" in q or ("sequence" in q and "translation" in q):
            aspects.append(
                [
                    "sequence to sequence",
                    "seq2seq",
                    "encoder decoder",
                    "encoder",
                    "decoder",
                    "neural machine translation",
                    "machine translation",
                ]
            )

        if "translation" in q:
            aspects.append(
                [
                    "translation",
                    "machine translation",
                    "neural machine translation",
                    "wmt",
                    "bleu",
                    "english german",
                    "english to german",
                    "english french",
                    "english to french",
                ]
            )

        if not aspects:
            return 1.0

        covered = sum(
            1
            for alternatives in aspects
            if any(term in searchable for term in alternatives)
        )

        return covered / max(len(aspects), 1)

    def _phrase_match_score(
        self,
        query: str,
        chunk: DocumentChunk,
        title: str | None = None,
    ) -> float:
        normalized_query = self._normalize_search_text(query)
        searchable = self._normalize_search_text(self._searchable_text(chunk, title))
        if not normalized_query or not searchable:
            return 0.0

        if normalized_query in searchable:
            return 1.0

        query_tokens = [
            token
            for token in normalized_query.split()
            if len(token) > 2 and token not in SEARCH_STOPWORDS
        ]
        if len(query_tokens) < 2:
            return 0.0

        best_window = 0
        max_window = min(len(query_tokens), 6)
        for window_size in range(max_window, 1, -1):
            for index in range(0, len(query_tokens) - window_size + 1):
                phrase = " ".join(query_tokens[index:index + window_size])
                if phrase in searchable:
                    best_window = window_size
                    break
            if best_window:
                break

        return best_window / max(len(query_tokens), 1)

    @staticmethod
    def _normalize_search_text(value: str | None) -> str:
        text = (value or "").replace("\u00a0", " ").lower()
        text = re.sub(r"seq\s*[- ]?\s*to\s*[- ]?\s*seq", "sequence to sequence", text)
        text = re.sub(r"sequence\s*[- ]\s*to\s*[- ]\s*sequence", "sequence to sequence", text)
        text = re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "", text)
        text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    def _normalized_term_in_text(self, term: str, normalized_text: str) -> bool:
        normalized_term = self._normalize_search_text(term)
        return bool(normalized_term and normalized_term in normalized_text)

    def _searchable_text(
        self,
        chunk: DocumentChunk,
        title: str | None = None,
    ) -> str:
        return " ".join(
            part
            for part in [
                title,
                chunk.section,
                getattr(chunk, "section_full_path", None),
                chunk.section_type,
                chunk.content,
            ]
            if isinstance(part, str) and part.strip()
        )

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

                if query_type != "technical_method" and self._same_section_root(item["chunk"], selected):
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
    def _clip_score(value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    @staticmethod
    def _search_tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(token) > 2 and token not in SEARCH_STOPWORDS
        }

    def _expanded_search_tokens(self, query: str) -> set[str]:
        tokens = self._search_tokens(query)
        q = (query or "").lower()
        is_technical_method_query = any(term in q for term in TECHNICAL_METHOD_TERMS)

        if any(term in q for term in ["optimization", "optimisation", "optimize", "optimise", "technique"]):
            tokens.update(
                {
                    "optimizer",
                    "adam",
                    "training",
                    "dropout",
                    "regularization",
                    "smoothing",
                    "beam",
                    "decoding",
                    "generation",
                    "schedule",
                    "warmup",
                }
            )

        if "sequence" in q or "translation" in q:
            tokens.update({"encoder", "decoder"})
            if not is_technical_method_query:
                tokens.update({"attention", "bleu", "wmt"})

        return tokens

    def _lexical_relevance_boost(self, query: str, chunk: DocumentChunk) -> float:
        query_tokens = self._expanded_search_tokens(query)
        if not query_tokens:
            return 0.0

        searchable = " ".join(
            part
            for part in [
                chunk.section,
                getattr(chunk, "section_full_path", None),
                chunk.section_type,
                chunk.content,
            ]
            if isinstance(part, str) and part.strip()
        )
        chunk_tokens = self._search_tokens(searchable)
        if not chunk_tokens:
            return 0.0

        overlap = len(query_tokens & chunk_tokens)
        coverage = overlap / max(len(query_tokens), 1)
        query_type = self._detect_query_type(query)
        if query_type == "technical_method":
            boost = min(coverage * 0.06 + overlap * 0.006, 0.08)
            boost += min(self._technical_method_signal_score(query, chunk) * 0.12, 0.14)
        else:
            boost = min(coverage * 0.12 + overlap * 0.01, 0.16)

        section_text = f"{chunk.section or ''} {getattr(chunk, 'section_full_path', '') or ''}".lower()
        if any(term in section_text for term in TECHNICAL_METHOD_SECTION_TERMS):
            boost += 0.03

        return min(boost, 0.20 if query_type == "technical_method" else 0.18)

    def _semantic_evidence_snippet(self, query: str, content: str | None, window: int = 520) -> str:
        if not content:
            return ""

        content_clean = " ".join(content.split())
        if len(content_clean) <= window:
            return content_clean

        query_tokens = self._expanded_search_tokens(query)
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

    @staticmethod
    def _normalize_page_match_text(value: str) -> str:
        text = (value or "").replace("...", " ")
        text = text.lower()
        text = re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "", text)
        text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    def _match_snippet_to_page(self, snippet: str, pages: list[dict]) -> int | None:
        normalized_snippet = self._normalize_page_match_text(snippet)
        if not normalized_snippet:
            return None

        snippet_tokens = [
            token
            for token in normalized_snippet.split()
            if len(token) > 2 and token not in SEARCH_STOPWORDS
        ]
        if len(snippet_tokens) < 5:
            return None

        best_match: tuple[float, int] | None = None
        for page in pages:
            page_num = self._page_number_from_record(page)
            if page_num is None:
                continue

            normalized_page = self._normalize_page_match_text(page.get("text") or "")
            if not normalized_page:
                continue

            if normalized_snippet in normalized_page:
                return page_num

            for window_size in (10, 8, 6):
                if len(snippet_tokens) < window_size:
                    continue
                for index in range(0, len(snippet_tokens) - window_size + 1):
                    phrase = " ".join(snippet_tokens[index:index + window_size])
                    if phrase in normalized_page:
                        return page_num

            page_tokens = set(normalized_page.split())
            overlap = sum(1 for token in snippet_tokens if token in page_tokens)
            coverage = overlap / max(len(snippet_tokens), 1)
            if coverage >= 0.72 and (
                best_match is None or coverage > best_match[0]
            ):
                best_match = (coverage, page_num)

        return best_match[1] if best_match else None

    @staticmethod
    def _page_number_from_record(page: dict) -> int | None:
        for key in ("page", "page_number", "page_no", "number"):
            value = page.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())

        page_index = page.get("page_index")
        if isinstance(page_index, int):
            return page_index + 1
        if isinstance(page_index, str) and page_index.strip().isdigit():
            return int(page_index.strip()) + 1

        return None

    def _load_pages_for_canonical(
        self,
        canonical_document_id,
        page_cache: dict[str, list[dict]],
    ) -> list[dict]:
        cache_key = str(canonical_document_id)
        if cache_key in page_cache:
            return page_cache[cache_key]

        paper = (
            self.db.query(PaperRecord)
            .filter(
                PaperRecord.canonical_document_id == canonical_document_id,
                PaperRecord.publication_status == "published",
                PaperRecord.page_text_json_storage_path.isnot(None),
            )
            .order_by(PaperRecord.created_at.asc())
            .first()
        )
        if not paper or not paper.page_text_json_storage_path:
            page_cache[cache_key] = []
            return []

        try:
            storage = StorageService()
            pages_bytes = storage.download_by_storage_path(paper.page_text_json_storage_path)
            pages = json.loads(pages_bytes.decode("utf-8"))
            if isinstance(pages, list):
                page_cache[cache_key] = pages
            elif isinstance(pages, dict) and isinstance(pages.get("pages"), list):
                page_cache[cache_key] = pages["pages"]
            else:
                page_cache[cache_key] = []
        except Exception as exc:
            logger.warning(
                "[search] Failed to load pages.json for canonical_id=%s error=%s",
                canonical_document_id,
                str(exc),
            )
            page_cache[cache_key] = []

        return page_cache[cache_key]

    def _resolve_result_pages(
        self,
        chunk: DocumentChunk,
        evidence_snippet: str,
        page_cache: dict[str, list[dict]],
    ) -> tuple[int | None, int | None]:
        if chunk.page_from is not None or chunk.page_to is not None:
            return chunk.page_from, chunk.page_to

        pages = self._load_pages_for_canonical(chunk.canonical_document_id, page_cache)
        matched_page = self._match_snippet_to_page(evidence_snippet, pages)
        if matched_page is None:
            return None, None

        return matched_page, matched_page

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
            page_cache: dict[str, list[dict]] = {}
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
                page_from, page_to = self._resolve_result_pages(
                    chunk,
                    snippet,
                    page_cache,
                )

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
                        page_from=page_from,
                        page_to=page_to,
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
