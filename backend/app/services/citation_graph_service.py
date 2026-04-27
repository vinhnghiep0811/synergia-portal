from __future__ import annotations

import copy
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.canonical_document import CanonicalDocument
from app.models.citation_edge import CitationEdge
from app.models.citation_mention import CitationMention
from app.models.citation_score_run import CitationScoreRun
from app.models.document_section import DocumentSection
from app.models.paper_record import PaperRecord

DOI_REGEX = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
NUMERIC_CITATION_REGEX = re.compile(r"\[(\d{1,3}(?:\s*[-,]\s*\d{1,3})*)\]")
AUTHOR_YEAR_CITATION_REGEX = re.compile(r"\(([^)]*?\b(?:19|20)\d{2}[a-z]?\b[^)]*)\)")
TOKEN_REGEX = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)

MAX_CONTEXT_SNIPPET_CHARS = 500
MAX_MENTION_CANDIDATES_PER_CHUNK = 200
MAX_AUTHOR_YEAR_SEGMENTS = 8
PAIRWISE_REFERENCE_MIN_COMBINED_SCORE = 0.70
PAIRWISE_REFERENCE_HIGH_TITLE_SCORE = 0.90
PAIRWISE_REFERENCE_MIXED_TITLE_SCORE = 0.74
PAIRWISE_REFERENCE_MIXED_AUTHOR_YEAR_SCORE = 0.35
PAIRWISE_REFERENCE_HIGH_AUTHOR_YEAR_SCORE = 0.85
PAIRWISE_REFERENCE_HIGH_AUTHOR_YEAR_TITLE_SCORE = 0.45
PAIRWISE_REFERENCE_MAX_NEW_LINKS_PER_SOURCE = 400
DECIMAL_STEP = Decimal("0.0001")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "we",
    "our",
}


@dataclass
class TargetDocumentInfo:
    canonical_id: UUID
    title: str
    abstract: str
    normalized_title: str
    title_tokens: set[str]
    doi_normalized: str | None
    publication_year: int | None
    author_surnames: set[str]


@dataclass
class TargetCatalog:
    by_id: dict[UUID, TargetDocumentInfo]
    by_doi: dict[str, TargetDocumentInfo]
    by_year: dict[int, list[TargetDocumentInfo]]
    all_targets: list[TargetDocumentInfo]


@dataclass
class ReferenceEntry:
    index: int | None
    raw_text: str
    doi: str | None
    title: str | None
    year: int | None
    author_surnames: set[str]
    target_id: UUID | None = None
    link_method: str | None = None
    doi_match: float = 0.0
    title_match: float = 0.0
    author_year_match: float = 0.0


@dataclass
class MentionCandidate:
    kind: str
    anchor_text: str
    span_start: int
    span_end: int
    numbers: list[int] = field(default_factory=list)
    doi: str | None = None
    author_year_text: str | None = None


@dataclass
class MentionLink:
    target_id: UUID | None
    link_method: str | None
    doi_match: float = 0.0
    title_match: float = 0.0
    author_year_match: float = 0.0
    anchor_text_override: str | None = None


class CitationGraphService:
    DEFAULT_ALGORITHM_VERSION = "citation-v1"

    DIVERSITY_HIGH_WEIGHT_SECTIONS = {
        "method",
        "evaluation",
        "results",
        "discussion",
        "conclusion",
    }

    COHERENCE_VERB_HINTS = {
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "use",
        "uses",
        "used",
        "using",
        "show",
        "shows",
        "showed",
        "shown",
        "improve",
        "improves",
        "improved",
        "outperform",
        "outperforms",
        "outperformed",
        "compare",
        "compares",
        "compared",
        "predict",
        "predicts",
        "predicted",
        "train",
        "trains",
        "trained",
        "evaluate",
        "evaluates",
        "evaluated",
        "propose",
        "proposes",
        "proposed",
    }

    SECTION_WEIGHTS = {
        "method": 1.00,
        "evaluation": 1.00,
        "results": 1.00,
        "discussion": 0.80,
        "conclusion": 0.80,
        "introduction": 0.60,
        "background": 0.60,
        "related_work": 0.45,
        "abstract": 0.35,
        "references": 0.00,
        "appendix": 0.00,
        "other": 0.50,
    }

    INTENT_SCORES = {
        "use_method": 1.00,
        "compare": 0.85,
        "baseline": 0.75,
        "support": 0.65,
        "background": 0.40,
        "mention_only": 0.20,
    }

    DEFAULT_WEIGHTS_JSON: dict[str, Any] = {
        "link_confidence": {
            "doi_match": 0.70,
            "title_match": 0.20,
            "author_year_match": 0.10,
        },
        "chunk_quality": {
            "length_score": 0.45,
            "clean_score": 0.30,
            "anchor_clarity": 0.15,
            "coherence_score": 0.10,
        },
        "mention_score": {
            "semantic_similarity": 0.35,
            "intent_score": 0.30,
            "section_weight": 0.25,
            "chunk_quality": 0.10,
            "link_confidence_gate": "multiply",
        },
        "edge_score": {
            "top3_mean_score": 0.60,
            "frequency_score": 0.20,
            "diversity_score": 0.15,
            "intent_edge_score": 0.05,
            "diversity_divisor": 3,
            "diversity_section_scope": "high_weight_only",
        },
        "section_weights": SECTION_WEIGHTS,
        "intent_scores": INTENT_SCORES,
    }

    def __init__(self, db: Session):
        self.db = db

    def score_graph(
        self,
        algorithm_version: str | None = None,
        source_canonical_ids: list[UUID] | None = None,
    ) -> CitationScoreRun:
        all_source_ids = self._resolve_source_canonical_ids(None)
        source_ids = self._resolve_source_canonical_ids(source_canonical_ids)
        if not source_ids:
            raise ValueError("No canonical documents available for citation scoring.")

        run_metadata = self._build_run_metadata(
            source_ids=source_ids,
            all_source_ids=all_source_ids,
        )

        run = self._create_running_run(
            algorithm_version or self.DEFAULT_ALGORITHM_VERSION,
            run_metadata=run_metadata,
        )

        try:
            source_docs = self._load_source_documents(source_ids)
            if not source_docs:
                raise ValueError("No source canonical documents found for citation scoring.")
            target_catalog = self._build_target_catalog()

            mention_rows: list[CitationMention] = []
            for source_doc in source_docs:
                mention_rows.extend(
                    self._build_mentions_for_source(
                        run_id=run.id,
                        source_document=source_doc,
                        target_catalog=target_catalog,
                    )
                )

            if mention_rows:
                self.db.add_all(mention_rows)
                self.db.flush()

            edge_rows = self._build_edges_from_mentions(
                run_id=run.id,
                algorithm_version=run.algorithm_version,
                mentions=mention_rows,
            )

            if edge_rows:
                self.db.add_all(edge_rows)

            run.processed_mentions = len(mention_rows)
            run.processed_edges = len(edge_rows)
            run.status = "completed"
            run.ended_at = datetime.now(timezone.utc)

            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)

            return run

        except Exception as exc:
            self.db.rollback()
            self._mark_run_failed(run_id=run.id, error_message=str(exc))
            raise

    def get_run(self, run_id: UUID) -> CitationScoreRun | None:
        return (
            self.db.query(CitationScoreRun)
            .filter(CitationScoreRun.id == run_id)
            .first()
        )

    def get_latest_completed_run(self, prefer_full_rebuild: bool = False) -> CitationScoreRun | None:
        query = (
            self.db.query(CitationScoreRun)
            .filter(CitationScoreRun.status == "completed")
            .order_by(CitationScoreRun.started_at.desc())
        )

        if not prefer_full_rebuild:
            return query.first()

        runs = query.limit(500).all()
        if not runs:
            return None

        for run in runs:
            if self._is_full_rebuild_run(run):
                return run

        return runs[0]

    def list_edges(
        self,
        canonical_document_id: UUID,
        direction: str,
        run_id: UUID | None = None,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> tuple[CitationScoreRun | None, list[CitationEdge]]:
        run = self._resolve_completed_run(run_id, prefer_full_rebuild=True)
        if not run:
            return None, []

        query = (
            self.db.query(CitationEdge)
            .options(
                selectinload(CitationEdge.source_canonical_document),
                selectinload(CitationEdge.target_canonical_document),
            )
            .filter(CitationEdge.run_id == run.id)
        )

        if direction == "incoming":
            query = query.filter(CitationEdge.target_canonical_id == canonical_document_id)
        else:
            query = query.filter(CitationEdge.source_canonical_id == canonical_document_id)

        if min_score > 0:
            query = query.filter(CitationEdge.citation_score >= self._to_decimal(min_score))

        edges = (
            query.order_by(CitationEdge.citation_score.desc(), CitationEdge.mention_count.desc())
            .limit(limit)
            .all()
        )

        return run, edges

    def list_mentions_for_edge(
        self,
        edge_id: UUID,
        limit: int = 100,
    ) -> tuple[CitationEdge | None, list[CitationMention]]:
        edge = (
            self.db.query(CitationEdge)
            .options(
                selectinload(CitationEdge.source_canonical_document),
                selectinload(CitationEdge.target_canonical_document),
            )
            .filter(CitationEdge.id == edge_id)
            .first()
        )

        if not edge:
            return None, []

        mentions = (
            self.db.query(CitationMention)
            .options(
                selectinload(CitationMention.source_chunk),
                selectinload(CitationMention.source_section),
                selectinload(CitationMention.target_canonical_document),
            )
            .filter(CitationMention.run_id == edge.run_id)
            .filter(CitationMention.source_canonical_id == edge.source_canonical_id)
            .filter(CitationMention.target_canonical_id == edge.target_canonical_id)
            .filter(CitationMention.is_internal.is_(True))
            .order_by(CitationMention.mention_score.desc(), CitationMention.created_at.asc())
            .limit(limit)
            .all()
        )

        return edge, mentions

    def list_network(
        self,
        run_id: UUID | None = None,
        limit_edges: int = 300,
        min_score: float = 0.0,
    ) -> tuple[CitationScoreRun | None, list[CitationEdge]]:
        run = self._resolve_completed_run(run_id, prefer_full_rebuild=True)
        if not run:
            return None, []

        query = (
            self.db.query(CitationEdge)
            .options(
                selectinload(CitationEdge.source_canonical_document),
                selectinload(CitationEdge.target_canonical_document),
            )
            .filter(CitationEdge.run_id == run.id)
        )

        if min_score > 0:
            query = query.filter(CitationEdge.citation_score >= self._to_decimal(min_score))

        edges = (
            query.order_by(CitationEdge.citation_score.desc(), CitationEdge.mention_count.desc())
            .limit(limit_edges)
            .all()
        )

        return run, edges

    def get_canonical_id_by_paper_id(self, paper_id: UUID) -> UUID:
        paper = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.id == paper_id)
            .first()
        )
        if not paper:
            raise ValueError("Paper not found.")

        if not paper.canonical_document_id:
            raise ValueError("Paper has not been linked to a canonical document yet.")

        return paper.canonical_document_id

    def _resolve_source_canonical_ids(
        self,
        source_canonical_ids: list[UUID] | None,
    ) -> list[UUID]:
        if source_canonical_ids:
            unique_ids = list(dict.fromkeys(source_canonical_ids))
            return unique_ids

        rows = (
            self.db.query(CanonicalDocument.id)
            .all()
        )
        return [row[0] for row in rows if row and row[0] is not None]

    def _build_run_metadata(
        self,
        source_ids: list[UUID],
        all_source_ids: list[UUID],
    ) -> dict[str, Any]:
        normalized_source_ids = sorted({str(item) for item in source_ids})
        normalized_all_source_ids = sorted({str(item) for item in all_source_ids})

        full_rebuild = (
            bool(normalized_all_source_ids)
            and set(normalized_source_ids) == set(normalized_all_source_ids)
        )

        return {
            "scope": "global" if full_rebuild else "subset",
            "full_rebuild": full_rebuild,
            "source_count": len(normalized_source_ids),
            "available_source_count": len(normalized_all_source_ids),
            "source_canonical_ids": normalized_source_ids,
        }

    def _create_running_run(
        self,
        algorithm_version: str,
        run_metadata: dict[str, Any] | None = None,
    ) -> CitationScoreRun:
        weights_json = copy.deepcopy(self.DEFAULT_WEIGHTS_JSON)
        if run_metadata:
            weights_json["_run_meta"] = run_metadata

        run = CitationScoreRun(
            algorithm_version=algorithm_version,
            weights_json=weights_json,
            status="running",
            processed_mentions=0,
            processed_edges=0,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _mark_run_failed(self, run_id: UUID, error_message: str) -> None:
        run = (
            self.db.query(CitationScoreRun)
            .filter(CitationScoreRun.id == run_id)
            .first()
        )
        if not run:
            return

        run.status = "failed"
        run.error_log = error_message[:4000]
        run.ended_at = datetime.now(timezone.utc)
        self.db.add(run)
        self.db.commit()

    def _extract_run_meta(self, run: CitationScoreRun) -> dict[str, Any]:
        weights_json = run.weights_json
        if not isinstance(weights_json, dict):
            return {}

        raw_meta = weights_json.get("_run_meta")
        if isinstance(raw_meta, dict):
            return raw_meta

        return {}

    def _is_full_rebuild_run(self, run: CitationScoreRun) -> bool:
        run_meta = self._extract_run_meta(run)
        full_rebuild = run_meta.get("full_rebuild")
        if isinstance(full_rebuild, bool):
            return full_rebuild

        return run_meta.get("scope") == "global"

    def _resolve_completed_run(
        self,
        run_id: UUID | None,
        prefer_full_rebuild: bool = False,
    ) -> CitationScoreRun | None:
        if run_id:
            run = (
                self.db.query(CitationScoreRun)
                .filter(CitationScoreRun.id == run_id)
                .first()
            )
            if run and run.status == "completed":
                return run
            return None

        return self.get_latest_completed_run(prefer_full_rebuild=prefer_full_rebuild)

    def _load_source_documents(self, source_ids: list[UUID]) -> list[CanonicalDocument]:
        docs = (
            self.db.query(CanonicalDocument)
            .options(
                selectinload(CanonicalDocument.document_chunks),
                selectinload(CanonicalDocument.document_sections),
            )
            .filter(CanonicalDocument.id.in_(source_ids))
            .all()
        )
        docs.sort(key=lambda item: str(item.id))
        return docs

    def _build_target_catalog(self) -> TargetCatalog:
        docs = self.db.query(CanonicalDocument).all()

        by_id: dict[UUID, TargetDocumentInfo] = {}
        by_doi: dict[str, TargetDocumentInfo] = {}
        by_year: dict[int, list[TargetDocumentInfo]] = defaultdict(list)
        all_targets: list[TargetDocumentInfo] = []

        for doc in docs:
            title = (doc.title or doc.title_candidate or "").strip()
            abstract = (doc.abstract or "").strip()
            normalized_title = self._normalize_title(title)
            title_tokens = set(self._tokenize(title))
            doi_normalized = self._normalize_doi(doc.doi)
            author_surnames = self._extract_author_surnames(doc.authors_json)

            info = TargetDocumentInfo(
                canonical_id=doc.id,
                title=title,
                abstract=abstract,
                normalized_title=normalized_title,
                title_tokens=title_tokens,
                doi_normalized=doi_normalized,
                publication_year=doc.publication_year,
                author_surnames=author_surnames,
            )

            by_id[doc.id] = info
            all_targets.append(info)

            if doi_normalized:
                by_doi[doi_normalized] = info

            if isinstance(doc.publication_year, int):
                by_year[doc.publication_year].append(info)

        return TargetCatalog(
            by_id=by_id,
            by_doi=by_doi,
            by_year=by_year,
            all_targets=all_targets,
        )

    def _build_mentions_for_source(
        self,
        run_id: UUID,
        source_document: CanonicalDocument,
        target_catalog: TargetCatalog,
    ) -> list[CitationMention]:
        source_sections = source_document.document_sections or []
        chunks = [
            chunk
            for chunk in (source_document.document_chunks or [])
            if bool((chunk.content or "").strip()) and bool(chunk.is_retrievable)
        ]
        chunks.sort(key=lambda item: item.chunk_index)

        reference_sections = [
            section
            for section in sorted(source_sections, key=lambda item: item.section_index)
            if self._is_reference_section(section)
        ]
        fallback_reference_section = reference_sections[0] if reference_sections else None

        reference_map, mapped_reference_entries = self._build_reference_map(
            sections=source_sections,
            source_document_id=source_document.id,
            target_catalog=target_catalog,
        )

        if not chunks and not reference_map and not mapped_reference_entries:
            return []

        mentions: list[CitationMention] = []
        resolved_target_ids: set[UUID] = set()

        for chunk in chunks:
            chunk_text = chunk.content or ""
            candidates = self._extract_mention_candidates(chunk_text)
            if not candidates:
                continue

            for candidate in candidates:
                links = self._resolve_candidate_links(
                    candidate=candidate,
                    chunk_text=chunk_text,
                    source_document_id=source_document.id,
                    reference_map=reference_map,
                    target_catalog=target_catalog,
                )

                if not links:
                    links = [MentionLink(target_id=None, link_method="unresolved")]

                context_snippet = self._build_context_snippet(
                    text=chunk_text,
                    start=candidate.span_start,
                    end=candidate.span_end,
                )

                section_type = self._normalize_section_type(chunk.section_type)
                section_weight = self._section_weight(section_type)
                intent_label, intent_score = self._infer_intent(context_snippet)
                chunk_quality = self._calculate_chunk_quality(context_snippet, candidate.kind)

                for link in links:
                    anchor_text = link.anchor_text_override or candidate.anchor_text
                    target_info = (
                        target_catalog.by_id.get(link.target_id)
                        if link.target_id is not None
                        else None
                    )

                    if target_info is not None:
                        semantic_similarity = self._semantic_similarity(
                            context_snippet,
                            f"{target_info.title} {target_info.abstract}".strip(),
                        )

                        title_match = max(
                            link.title_match,
                            self._title_similarity(context_snippet, target_info.title),
                        )

                        link_confidence = self._compute_link_confidence(
                            doi_match=link.doi_match,
                            title_match=title_match,
                            author_year_match=link.author_year_match,
                        )

                        is_internal = True
                    else:
                        semantic_similarity = 0.0
                        link_confidence = 0.0
                        is_internal = False

                    if is_internal and link.target_id is not None:
                        resolved_target_ids.add(link.target_id)

                    mention_score = self._compute_mention_score(
                        semantic_similarity=semantic_similarity,
                        intent_score=intent_score,
                        section_weight=section_weight,
                        chunk_quality=chunk_quality,
                        link_confidence=link_confidence,
                    )

                    mentions.append(
                        CitationMention(
                            run_id=run_id,
                            source_canonical_id=source_document.id,
                            target_canonical_id=link.target_id,
                            source_chunk_id=chunk.id,
                            source_section_id=chunk.section_id,
                            anchor_text=anchor_text[:255] if anchor_text else None,
                            context_snippet=context_snippet,
                            page_from=chunk.page_from,
                            page_to=chunk.page_to,
                            section_type=section_type,
                            section_weight=self._to_decimal(section_weight),
                            link_method=(link.link_method or "unresolved")[:50],
                            link_confidence=self._to_decimal(link_confidence),
                            semantic_similarity=self._to_decimal(semantic_similarity),
                            intent_label=intent_label,
                            intent_score=self._to_decimal(intent_score),
                            chunk_quality=self._to_decimal(chunk_quality),
                            mention_score=self._to_decimal(mention_score),
                            is_internal=is_internal,
                        )
                    )

        fallback_mentions = self._build_reference_fallback_mentions(
            run_id=run_id,
            source_document_id=source_document.id,
            target_catalog=target_catalog,
            reference_map=reference_map,
            resolved_target_ids=resolved_target_ids,
            reference_section=fallback_reference_section,
        )
        if fallback_mentions:
            mentions.extend(fallback_mentions)

        pairwise_mentions = self._build_pairwise_reference_mentions(
            run_id=run_id,
            source_document_id=source_document.id,
            target_catalog=target_catalog,
            reference_entries=mapped_reference_entries,
            resolved_target_ids=resolved_target_ids,
            reference_section=fallback_reference_section,
        )
        if pairwise_mentions:
            mentions.extend(pairwise_mentions)

        return mentions

    def _build_pairwise_reference_mentions(
        self,
        run_id: UUID,
        source_document_id: UUID,
        target_catalog: TargetCatalog,
        reference_entries: list[ReferenceEntry],
        resolved_target_ids: set[UUID],
        reference_section: DocumentSection | None,
    ) -> list[CitationMention]:
        if not reference_entries:
            return []

        pairwise_mentions: list[CitationMention] = []

        # Enforce source->all-target checking so each source can discover missing
        # intermediate edges even when anchor extraction is incomplete.
        for target in target_catalog.all_targets:
            target_id = target.canonical_id
            if target_id == source_document_id or target_id in resolved_target_ids:
                continue

            (
                best_entry,
                doi_match,
                title_match,
                author_year_match,
                combined_score,
            ) = self._best_pairwise_reference_match(
                reference_entries=reference_entries,
                target=target,
            )

            if best_entry is None:
                continue

            if not self._is_pairwise_reference_match_confident(
                doi_match=doi_match,
                title_match=title_match,
                author_year_match=author_year_match,
                combined_score=combined_score,
            ):
                continue

            context_snippet = self._truncate_snippet(best_entry.raw_text)
            section_type = "references"
            section_weight = self._section_weight(section_type)
            intent_label = "background"
            intent_score = self.INTENT_SCORES[intent_label]

            chunk_quality = self._calculate_chunk_quality(context_snippet, "author_year")
            semantic_similarity = self._semantic_similarity(
                context_snippet,
                f"{target.title} {target.abstract}".strip(),
            )

            title_match = max(
                title_match,
                self._title_similarity(best_entry.title or context_snippet, target.title),
            )
            link_confidence = self._compute_link_confidence(
                doi_match=doi_match,
                title_match=title_match,
                author_year_match=author_year_match,
            )

            mention_score = self._compute_mention_score(
                semantic_similarity=semantic_similarity,
                intent_score=intent_score,
                section_weight=section_weight,
                chunk_quality=chunk_quality,
                link_confidence=link_confidence,
            )

            anchor_text = (
                f"[{best_entry.index}]"
                if best_entry.index is not None
                else (best_entry.doi or best_entry.title or best_entry.raw_text[:80])
            )

            pairwise_mentions.append(
                CitationMention(
                    run_id=run_id,
                    source_canonical_id=source_document_id,
                    target_canonical_id=target_id,
                    source_chunk_id=None,
                    source_section_id=reference_section.id if reference_section else None,
                    anchor_text=anchor_text[:255] if anchor_text else None,
                    context_snippet=context_snippet,
                    page_from=reference_section.page_from if reference_section else None,
                    page_to=reference_section.page_to if reference_section else None,
                    section_type=section_type,
                    section_weight=self._to_decimal(section_weight),
                    link_method="pairwise_reference_scan",
                    link_confidence=self._to_decimal(link_confidence),
                    semantic_similarity=self._to_decimal(semantic_similarity),
                    intent_label=intent_label,
                    intent_score=self._to_decimal(intent_score),
                    chunk_quality=self._to_decimal(chunk_quality),
                    mention_score=self._to_decimal(mention_score),
                    is_internal=True,
                )
            )

            resolved_target_ids.add(target_id)

            if len(pairwise_mentions) >= PAIRWISE_REFERENCE_MAX_NEW_LINKS_PER_SOURCE:
                break

        return pairwise_mentions

    def _best_pairwise_reference_match(
        self,
        reference_entries: list[ReferenceEntry],
        target: TargetDocumentInfo,
    ) -> tuple[ReferenceEntry | None, float, float, float, float]:
        best_entry: ReferenceEntry | None = None
        best_doi_match = 0.0
        best_title_match = 0.0
        best_author_year_match = 0.0
        best_combined = 0.0

        for entry in reference_entries:
            doi_match = (
                1.0
                if target.doi_normalized and entry.doi == target.doi_normalized
                else 0.0
            )
            title_match = self._title_similarity(entry.title or entry.raw_text, target.title)
            author_year_match = self._author_year_match(entry, target)

            combined = max(
                doi_match,
                (0.75 * title_match) + (0.25 * author_year_match),
                (0.65 * author_year_match) + (0.35 * title_match),
            )

            if combined > best_combined:
                best_entry = entry
                best_doi_match = doi_match
                best_title_match = title_match
                best_author_year_match = author_year_match
                best_combined = combined

        return (
            best_entry,
            best_doi_match,
            best_title_match,
            best_author_year_match,
            best_combined,
        )

    def _is_pairwise_reference_match_confident(
        self,
        doi_match: float,
        title_match: float,
        author_year_match: float,
        combined_score: float,
    ) -> bool:
        if doi_match >= 1.0:
            return True

        if title_match >= PAIRWISE_REFERENCE_HIGH_TITLE_SCORE:
            return True

        if (
            title_match >= PAIRWISE_REFERENCE_MIXED_TITLE_SCORE
            and author_year_match >= PAIRWISE_REFERENCE_MIXED_AUTHOR_YEAR_SCORE
        ):
            return True

        if (
            author_year_match >= PAIRWISE_REFERENCE_HIGH_AUTHOR_YEAR_SCORE
            and title_match >= PAIRWISE_REFERENCE_HIGH_AUTHOR_YEAR_TITLE_SCORE
        ):
            return True

        return combined_score >= PAIRWISE_REFERENCE_MIN_COMBINED_SCORE

    def _build_reference_fallback_mentions(
        self,
        run_id: UUID,
        source_document_id: UUID,
        target_catalog: TargetCatalog,
        reference_map: dict[int, ReferenceEntry],
        resolved_target_ids: set[UUID],
        reference_section: DocumentSection | None,
    ) -> list[CitationMention]:
        fallback_mentions: list[CitationMention] = []

        for ref_index in sorted(reference_map.keys()):
            ref = reference_map[ref_index]
            target_id = ref.target_id
            if target_id is None or target_id == source_document_id:
                continue

            if target_id in resolved_target_ids:
                continue

            if not self._should_create_reference_fallback(ref):
                continue

            target_info = target_catalog.by_id.get(target_id)
            if target_info is None:
                continue

            context_snippet = self._truncate_snippet(ref.raw_text)
            section_type = "references"
            section_weight = self._section_weight(section_type)

            intent_label = "background"
            intent_score = self.INTENT_SCORES[intent_label]
            chunk_quality = self._calculate_chunk_quality(context_snippet, "author_year")
            semantic_similarity = self._semantic_similarity(
                context_snippet,
                f"{target_info.title} {target_info.abstract}".strip(),
            )

            title_match = max(
                ref.title_match,
                self._title_similarity(ref.title or context_snippet, target_info.title),
            )
            link_confidence = self._compute_link_confidence(
                doi_match=ref.doi_match,
                title_match=title_match,
                author_year_match=ref.author_year_match,
            )

            mention_score = self._compute_mention_score(
                semantic_similarity=semantic_similarity,
                intent_score=intent_score,
                section_weight=section_weight,
                chunk_quality=chunk_quality,
                link_confidence=link_confidence,
            )

            anchor_text = (
                f"[{ref.index}]"
                if ref.index is not None
                else (ref.doi or ref.title or ref.raw_text[:80])
            )

            fallback_mentions.append(
                CitationMention(
                    run_id=run_id,
                    source_canonical_id=source_document_id,
                    target_canonical_id=target_id,
                    source_chunk_id=None,
                    source_section_id=reference_section.id if reference_section else None,
                    anchor_text=anchor_text[:255] if anchor_text else None,
                    context_snippet=context_snippet,
                    page_from=reference_section.page_from if reference_section else None,
                    page_to=reference_section.page_to if reference_section else None,
                    section_type=section_type,
                    section_weight=self._to_decimal(section_weight),
                    link_method=(f"reference_fallback_{ref.link_method or 'mapped'}")[:50],
                    link_confidence=self._to_decimal(link_confidence),
                    semantic_similarity=self._to_decimal(semantic_similarity),
                    intent_label=intent_label,
                    intent_score=self._to_decimal(intent_score),
                    chunk_quality=self._to_decimal(chunk_quality),
                    mention_score=self._to_decimal(mention_score),
                    is_internal=True,
                )
            )

            resolved_target_ids.add(target_id)

        return fallback_mentions

    def _should_create_reference_fallback(self, ref: ReferenceEntry) -> bool:
        if ref.target_id is None:
            return False

        if ref.link_method == "doi_exact":
            return True

        if ref.link_method == "title_fuzzy":
            return ref.title_match >= 0.82

        if ref.link_method == "author_year":
            return ref.author_year_match >= 0.55

        return False

    def _build_reference_map(
        self,
        sections: list[DocumentSection],
        source_document_id: UUID,
        target_catalog: TargetCatalog,
    ) -> tuple[dict[int, ReferenceEntry], list[ReferenceEntry]]:
        reference_lines: list[str] = []

        for section in sorted(sections, key=lambda item: item.section_index):
            if not self._is_reference_section(section):
                continue

            for line in (section.content or "").splitlines():
                normalized = re.sub(r"\s+", " ", line).strip()
                if normalized:
                    reference_lines.append(normalized)

        if not reference_lines:
            return {}, []

        entries = self._parse_reference_entries(reference_lines)
        index_map: dict[int, ReferenceEntry] = {}
        mapped_entries: list[ReferenceEntry] = []

        for entry in entries:
            mapped = self._map_reference_entry_to_target(
                entry=entry,
                source_document_id=source_document_id,
                target_catalog=target_catalog,
            )
            mapped_entries.append(mapped)
            if mapped.index is not None and mapped.index not in index_map:
                index_map[mapped.index] = mapped

        return index_map, mapped_entries

    def _is_reference_section(self, section: DocumentSection) -> bool:
        section_type = self._normalize_section_type(section.section_type)
        section_name = (section.section_name or "").strip().lower()

        if section_type == "references":
            return True

        return "reference" in section_name or "bibliograph" in section_name

    def _parse_reference_entries(self, reference_lines: list[str]) -> list[ReferenceEntry]:
        entries: list[ReferenceEntry] = []
        current_index: int | None = None
        current_lines: list[str] = []
        unnumbered_counter = 0

        def flush_current() -> None:
            nonlocal current_index, current_lines, unnumbered_counter
            if not current_lines:
                return

            text = re.sub(r"\s+", " ", " ".join(current_lines)).strip()
            current_lines = []

            if len(text) < 20:
                current_index = None
                return

            index = current_index
            if index is None:
                unnumbered_counter += 1
                index = unnumbered_counter

            doi = self._extract_doi(text)
            year = self._extract_year(text)
            title = self._extract_reference_title(text)
            author_surnames = self._extract_reference_author_surnames(text)

            entries.append(
                ReferenceEntry(
                    index=index,
                    raw_text=text,
                    doi=doi,
                    title=title,
                    year=year,
                    author_surnames=author_surnames,
                )
            )

            current_index = None

        for raw_line in reference_lines:
            line = raw_line.strip()
            if line.startswith("- ") or line.startswith("* "):
                line = line[2:].strip()

            if not line:
                if current_lines:
                    flush_current()
                continue

            start_match = re.match(r"^(?:\[(\d{1,3})\]|(\d{1,3})[\).])\s+(.*)$", line)

            if start_match:
                flush_current()
                current_index = int(start_match.group(1) or start_match.group(2))
                current_lines = [start_match.group(3)]
                continue

            if current_lines and self._looks_like_new_reference_boundary(line):
                flush_current()
                current_lines = [line]
                continue

            if not current_lines:
                current_lines = [line]
            else:
                current_lines.append(line)

        flush_current()

        return entries

    def _looks_like_new_reference_boundary(self, line: str) -> bool:
        has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", line))
        has_comma = "," in line
        return has_year and has_comma and len(line) > 30

    def _map_reference_entry_to_target(
        self,
        entry: ReferenceEntry,
        source_document_id: UUID,
        target_catalog: TargetCatalog,
    ) -> ReferenceEntry:
        if entry.doi:
            by_doi = target_catalog.by_doi.get(entry.doi)
            if by_doi and by_doi.canonical_id != source_document_id:
                entry.target_id = by_doi.canonical_id
                entry.link_method = "doi_exact"
                entry.doi_match = 1.0
                entry.title_match = self._title_similarity(entry.title or "", by_doi.title)
                entry.author_year_match = self._author_year_match(entry, by_doi)
                return entry

        if entry.title:
            best_target: TargetDocumentInfo | None = None
            best_score = 0.0
            best_title_match = 0.0
            best_author_year_match = 0.0

            for target in target_catalog.all_targets:
                if target.canonical_id == source_document_id:
                    continue

                title_match = self._title_similarity(entry.title, target.title)
                author_year_match = self._author_year_match(entry, target)
                score = 0.80 * title_match + 0.20 * author_year_match

                if score > best_score:
                    best_score = score
                    best_target = target
                    best_title_match = title_match
                    best_author_year_match = author_year_match

            if best_target and best_title_match >= 0.78:
                entry.target_id = best_target.canonical_id
                entry.link_method = "title_fuzzy"
                entry.title_match = best_title_match
                entry.author_year_match = best_author_year_match
                return entry

        if entry.year and entry.author_surnames:
            year_candidates = target_catalog.by_year.get(entry.year, [])
            best_target: TargetDocumentInfo | None = None
            best_overlap = 0.0

            for target in year_candidates:
                if target.canonical_id == source_document_id:
                    continue

                overlap = self._surname_overlap(entry.author_surnames, target.author_surnames)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_target = target

            if best_target and best_overlap >= 0.45:
                entry.target_id = best_target.canonical_id
                entry.link_method = "author_year"
                entry.author_year_match = best_overlap

        return entry

    def _extract_mention_candidates(self, text: str) -> list[MentionCandidate]:
        candidates: list[MentionCandidate] = []

        for match in DOI_REGEX.finditer(text):
            candidates.append(
                MentionCandidate(
                    kind="doi",
                    anchor_text=match.group(0),
                    span_start=match.start(),
                    span_end=match.end(),
                    doi=match.group(0),
                )
            )

        for match in NUMERIC_CITATION_REGEX.finditer(text):
            numbers = self._parse_reference_numbers(match.group(1))
            if not numbers:
                continue

            candidates.append(
                MentionCandidate(
                    kind="numeric",
                    anchor_text=match.group(0),
                    span_start=match.start(),
                    span_end=match.end(),
                    numbers=numbers,
                )
            )

        for match in AUTHOR_YEAR_CITATION_REGEX.finditer(text):
            raw = (match.group(1) or "").strip()
            segments = self._split_author_year_segments(raw)
            for segment in segments:
                candidates.append(
                    MentionCandidate(
                        kind="author_year",
                        anchor_text=f"({segment})",
                        span_start=match.start(),
                        span_end=match.end(),
                        author_year_text=segment,
                    )
                )

        unique: dict[tuple[str, int, int, str], MentionCandidate] = {}
        for item in candidates:
            key = (item.kind, item.span_start, item.span_end, item.anchor_text)
            unique[key] = item

        ordered = sorted(unique.values(), key=lambda item: (item.span_start, item.span_end))
        return ordered[:MAX_MENTION_CANDIDATES_PER_CHUNK]

    def _split_author_year_segments(self, raw: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", raw or "").strip()
        if not cleaned:
            return []

        segments = [
            segment.strip(" ;,.")
            for segment in re.split(r"\s*;\s*", cleaned)
            if segment.strip(" ;,.")
        ]

        normalized_segments: list[str] = []
        for segment in segments:
            candidate = re.sub(
                r"^(?:see\s+also|see|cf\.|e\.g\.|i\.e\.)\s+",
                "",
                segment,
                flags=re.IGNORECASE,
            ).strip()
            if not self._looks_like_author_year_anchor(candidate):
                continue
            normalized_segments.append(candidate)

        if normalized_segments:
            return normalized_segments[:MAX_AUTHOR_YEAR_SEGMENTS]

        if self._looks_like_author_year_anchor(cleaned):
            return [cleaned]

        return []

    def _parse_reference_numbers(self, raw: str) -> list[int]:
        numbers: list[int] = []
        for token in raw.split(","):
            part = token.strip()
            if not part:
                continue

            if "-" in part:
                bounds = [x.strip() for x in part.split("-", 1)]
                if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                    continue

                start = int(bounds[0])
                end = int(bounds[1])
                if end < start:
                    start, end = end, start

                if end - start > 20:
                    continue

                numbers.extend(list(range(start, end + 1)))
                continue

            if part.isdigit():
                numbers.append(int(part))

        deduped = []
        seen = set()
        for value in numbers:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)

        return deduped[:12]

    def _looks_like_author_year_anchor(self, raw: str) -> bool:
        if len(raw) > 140:
            return False

        if DOI_REGEX.search(raw):
            return False

        if not re.search(r"\b(?:19|20)\d{2}[a-z]?\b", raw):
            return False

        has_letters = bool(re.search(r"[A-Za-z]", raw))
        return has_letters

    def _resolve_candidate_links(
        self,
        candidate: MentionCandidate,
        chunk_text: str,
        source_document_id: UUID,
        reference_map: dict[int, ReferenceEntry],
        target_catalog: TargetCatalog,
    ) -> list[MentionLink]:
        if candidate.kind == "doi":
            doi_normalized = self._normalize_doi(candidate.doi)
            target = target_catalog.by_doi.get(doi_normalized or "") if doi_normalized else None
            if target and target.canonical_id != source_document_id:
                return [
                    MentionLink(
                        target_id=target.canonical_id,
                        link_method="doi_exact",
                        doi_match=1.0,
                    )
                ]

            return [MentionLink(target_id=None, link_method="doi_unresolved")]

        if candidate.kind == "numeric":
            links: list[MentionLink] = []

            for number in candidate.numbers:
                ref = reference_map.get(number)

                if ref and ref.target_id and ref.target_id != source_document_id:
                    links.append(
                        MentionLink(
                            target_id=ref.target_id,
                            link_method=f"ref_index_{ref.link_method or 'mapped'}",
                            doi_match=ref.doi_match,
                            title_match=ref.title_match,
                            author_year_match=ref.author_year_match,
                            anchor_text_override=f"[{number}]",
                        )
                    )
                    continue

                links.append(
                    MentionLink(
                        target_id=None,
                        link_method="ref_index_unresolved",
                        anchor_text_override=f"[{number}]",
                    )
                )

            deduped: dict[tuple[UUID | None, str | None, str | None], MentionLink] = {}
            for link in links:
                key = (link.target_id, link.link_method, link.anchor_text_override)
                deduped[key] = link

            return list(deduped.values())

        if candidate.kind == "author_year":
            context = self._build_context_snippet(
                text=chunk_text,
                start=candidate.span_start,
                end=candidate.span_end,
            )
            return self._resolve_author_year_link(
                source_document_id=source_document_id,
                author_year_text=candidate.author_year_text or "",
                context_snippet=context,
                target_catalog=target_catalog,
            )

        return [MentionLink(target_id=None, link_method="unresolved")]

    def _resolve_author_year_link(
        self,
        source_document_id: UUID,
        author_year_text: str,
        context_snippet: str,
        target_catalog: TargetCatalog,
    ) -> list[MentionLink]:
        year = self._extract_year(author_year_text)
        surnames = self._extract_surnames_from_author_year(author_year_text)

        if year:
            candidates = target_catalog.by_year.get(year, [])
        else:
            candidates = target_catalog.all_targets

        scored_candidates: list[tuple[TargetDocumentInfo, float, float, float]] = []

        for target in candidates:
            if target.canonical_id == source_document_id:
                continue

            author_year_match = self._surname_overlap(surnames, target.author_surnames)
            title_match = self._title_similarity(context_snippet, target.title)

            combined = 0.70 * author_year_match + 0.30 * title_match
            if combined >= 0.40:
                scored_candidates.append(
                    (target, combined, title_match, author_year_match)
                )

        if not scored_candidates:
            return [MentionLink(target_id=None, link_method="author_year_unresolved")]

        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        top_score = scored_candidates[0][1]
        adaptive_threshold = max(0.40, top_score - 0.08)

        links: list[MentionLink] = []
        for target, combined, title_match, author_year_match in scored_candidates:
            if combined < adaptive_threshold:
                continue

            links.append(
                MentionLink(
                    target_id=target.canonical_id,
                    link_method="author_year_heuristic",
                    title_match=title_match,
                    author_year_match=author_year_match,
                )
            )

            if len(links) >= 3:
                break

        if links:
            return links

        return [MentionLink(target_id=None, link_method="author_year_unresolved")]

    def _build_context_snippet(self, text: str, start: int, end: int) -> str:
        if not text:
            return ""

        sentence_matches = list(re.finditer(r"[^.!?]+[.!?]?", text))
        if not sentence_matches:
            return self._truncate_snippet(text[max(0, start - 120): end + 120])

        sentence_index = None
        for idx, match in enumerate(sentence_matches):
            if match.start() <= start <= match.end():
                sentence_index = idx
                break

        if sentence_index is None:
            return self._truncate_snippet(text[max(0, start - 120): end + 120])

        left = max(0, sentence_index - 1)
        right = min(len(sentence_matches), sentence_index + 2)
        snippet = " ".join(m.group(0).strip() for m in sentence_matches[left:right])
        return self._truncate_snippet(snippet)

    def _truncate_snippet(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= MAX_CONTEXT_SNIPPET_CHARS:
            return normalized

        cut = normalized[:MAX_CONTEXT_SNIPPET_CHARS]
        last_break = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
        if last_break > 120:
            return cut[:last_break].strip()

        return cut.strip()

    def _infer_intent(self, snippet: str) -> tuple[str, float]:
        lowered = (snippet or "").lower()

        if any(token in lowered for token in ["we use", "using ", "adopt", "based on", "following ", "build on", "built on"]):
            label = "use_method"
        elif any(token in lowered for token in ["compare", "compared", "versus", "vs.", "outperform", "better than"]):
            label = "compare"
        elif "baseline" in lowered:
            label = "baseline"
        elif any(token in lowered for token in ["support", "consistent with", "in line with"]):
            label = "support"
        elif any(token in lowered for token in ["related work", "background", "survey", "for example", "e.g."]):
            label = "background"
        else:
            label = "mention_only"

        return label, self.INTENT_SCORES[label]

    def _calculate_chunk_quality(self, snippet: str, anchor_kind: str) -> float:
        text = snippet or ""

        len_score = self._clip01((len(text) - 40) / 180) if text else 0.0

        if text:
            clean_chars = sum(1 for ch in text if ch.isalnum() or ch.isspace() or ch in ",.;:?!()[]-" )
            clean_score = clean_chars / len(text)
        else:
            clean_score = 0.0

        anchor_clarity_map = {
            "doi": 1.0,
            "numeric": 0.9,
            "author_year": 0.75,
        }
        anchor_clarity = anchor_clarity_map.get(anchor_kind, 0.5)
        coherence_score = self._coherence_score(text)

        quality = (
            (0.45 * len_score)
            + (0.30 * clean_score)
            + (0.15 * anchor_clarity)
            + (0.10 * coherence_score)
        )
        return self._clip01(quality)

    def _coherence_score(self, snippet: str) -> float:
        text = re.sub(r"\s+", " ", snippet or "").strip()
        if not text:
            return 0.0

        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", text)
            if part.strip()
        ]
        if not sentences:
            sentences = [text]

        sentence_scores: list[float] = []
        for sentence in sentences[:3]:
            tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence.lower())
            if not tokens:
                sentence_scores.append(0.0)
                continue

            length_score = self._clip01((len(tokens) - 4) / 10)
            has_verb = any(
                token in self.COHERENCE_VERB_HINTS
                or token.endswith("ed")
                or token.endswith("ing")
                for token in tokens
            )
            terminal_score = 1.0 if sentence[-1] in ".!?" else 0.6

            sentence_scores.append(
                (0.45 * length_score)
                + (0.35 * (1.0 if has_verb else 0.0))
                + (0.20 * terminal_score)
            )

        base_score = sum(sentence_scores) / len(sentence_scores)

        delimiter_penalty = 0.0
        delimiter_pairs = (("(", ")"), ("[", "]"), ("{", "}"))
        for left, right in delimiter_pairs:
            imbalance = abs(text.count(left) - text.count(right))
            delimiter_penalty += min(0.10, 0.05 * imbalance)

        return self._clip01(base_score - delimiter_penalty)

    def _compute_link_confidence(
        self,
        doi_match: float,
        title_match: float,
        author_year_match: float,
    ) -> float:
        score = (0.70 * doi_match) + (0.20 * title_match) + (0.10 * author_year_match)
        return self._clip01(score)

    def _compute_mention_score(
        self,
        semantic_similarity: float,
        intent_score: float,
        section_weight: float,
        chunk_quality: float,
        link_confidence: float,
    ) -> float:
        base_score = (
            (0.35 * semantic_similarity)
            + (0.30 * intent_score)
            + (0.25 * section_weight)
            + (0.10 * chunk_quality)
        )
        return self._clip01(base_score) * self._clip01(link_confidence)

    def _build_edges_from_mentions(
        self,
        run_id: UUID,
        algorithm_version: str,
        mentions: list[CitationMention],
    ) -> list[CitationEdge]:
        grouped: dict[tuple[UUID, UUID], list[CitationMention]] = defaultdict(list)

        for mention in mentions:
            if not mention.is_internal:
                continue
            if not mention.target_canonical_id:
                continue
            if mention.source_canonical_id == mention.target_canonical_id:
                continue

            key = (mention.source_canonical_id, mention.target_canonical_id)
            grouped[key].append(mention)

        edges: list[CitationEdge] = []

        for (source_id, target_id), items in grouped.items():
            sorted_mentions = sorted(
                items,
                key=lambda mention: float(mention.mention_score or 0),
                reverse=True,
            )

            top_mentions = sorted_mentions[:3]
            mention_count = len(sorted_mentions)

            top3_mean_score = (
                sum(float(item.mention_score or 0) for item in top_mentions) / len(top_mentions)
                if top_mentions
                else 0.0
            )

            frequency_score = min(1.0, math.log(1 + mention_count) / math.log(11))

            section_keys = {
                self._normalize_section_type(item.section_type)
                for item in sorted_mentions
                if self._normalize_section_type(item.section_type)
                in self.DIVERSITY_HIGH_WEIGHT_SECTIONS
            }
            diversity_score = min(1.0, len(section_keys) / 3)

            intent_edge_score = (
                sum(float(item.intent_score or 0) for item in top_mentions) / len(top_mentions)
                if top_mentions
                else 0.0
            )

            citation_score = self._clip01(
                (0.60 * top3_mean_score)
                + (0.20 * frequency_score)
                + (0.15 * diversity_score)
                + (0.05 * intent_edge_score)
            )

            evidence_json = [self._mention_to_evidence(item) for item in top_mentions]

            edges.append(
                CitationEdge(
                    run_id=run_id,
                    algorithm_version=algorithm_version,
                    source_canonical_id=source_id,
                    target_canonical_id=target_id,
                    mention_count=mention_count,
                    top3_mean_score=self._to_decimal(top3_mean_score),
                    frequency_score=self._to_decimal(frequency_score),
                    diversity_score=self._to_decimal(diversity_score),
                    intent_edge_score=self._to_decimal(intent_edge_score),
                    citation_score=self._to_decimal(citation_score),
                    score_band=self._score_band(citation_score),
                    evidence_json=evidence_json,
                )
            )

        return edges

    def _mention_to_evidence(self, mention: CitationMention) -> dict[str, Any]:
        return {
            "mention_id": str(mention.id) if mention.id else None,
            "anchor_text": mention.anchor_text,
            "context_snippet": mention.context_snippet,
            "page_from": mention.page_from,
            "page_to": mention.page_to,
            "section_type": mention.section_type,
            "section_weight": float(mention.section_weight or 0),
            "intent_label": mention.intent_label,
            "link_method": mention.link_method,
            "mention_score": float(mention.mention_score or 0),
        }

    def _score_band(self, score: float) -> str:
        if score >= 0.67:
            return "high"
        if score >= 0.34:
            return "medium"
        return "low"

    def _section_weight(self, section_type: str | None) -> float:
        normalized = self._normalize_section_type(section_type)
        return self.SECTION_WEIGHTS.get(normalized, self.SECTION_WEIGHTS["other"])

    def _normalize_section_type(self, section_type: str | None) -> str:
        raw = (section_type or "").strip().lower()
        if not raw:
            return "other"

        aliases = {
            "methods": "method",
            "methodology": "method",
            "experiments": "evaluation",
            "experiment": "evaluation",
            "conclusions": "conclusion",
            "related works": "related_work",
        }
        return aliases.get(raw, raw)

    def _extract_doi(self, text: str) -> str | None:
        match = DOI_REGEX.search(text or "")
        if not match:
            return None
        return self._normalize_doi(match.group(0))

    def _normalize_doi(self, doi: str | None) -> str | None:
        if not doi:
            return None

        normalized = doi.strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]

        normalized = normalized.strip().strip(".,;)")
        return normalized or None

    def _extract_year(self, text: str | None) -> int | None:
        if not text:
            return None

        match = re.search(r"\b(19|20)\d{2}\b", text)
        if not match:
            return None

        return int(match.group(0))

    def _extract_reference_title(self, text: str) -> str | None:
        quoted_match = re.search(r"[\"\u201c\u201d]([^\"\u201c\u201d]{8,300})[\"\u201c\u201d]", text)
        if quoted_match:
            return quoted_match.group(1).strip()

        cleaned = re.sub(r"^(?:\[\d+\]|\d+[\).])\s*", "", text).strip()
        if cleaned.startswith("- ") or cleaned.startswith("* "):
            cleaned = cleaned[2:].strip()

        cleaned = DOI_REGEX.sub("", cleaned)
        cleaned = re.sub(r"https?://\S+", "", cleaned)

        cleaned = cleaned.strip(" .;:-")
        if not cleaned:
            return None

        segments = [segment.strip(" .;:-") for segment in re.split(r"\.\s+", cleaned) if segment.strip()]

        venue_keywords = {
            "vol",
            "pp",
            "doi",
            "arxiv",
            "corr",
            "proc",
            "conference",
            "journal",
            "transactions",
            "workshop",
            "acl",
            "emnlp",
            "naacl",
            "nips",
            "icml",
            "iclr",
            "aaai",
            "ieee",
            "pages",
            "preprint",
            "advances",
            "proceedings",
        }

        for segment in segments:
            lowered = segment.lower()
            if len(segment.split()) < 4:
                continue

            if any(token in lowered for token in venue_keywords):
                continue

            if re.search(r"\b(?:19|20)\d{2}\b", segment):
                continue

            comma_count = segment.count(",")
            word_count = len(segment.split())
            if comma_count >= 3 and word_count <= 12:
                continue

            return segment[:300]

        fallback_candidates = [
            segment
            for segment in segments
            if len(segment.split()) >= 4
            and not re.search(r"\b(?:19|20)\d{2}\b", segment)
            and not any(token in segment.lower() for token in venue_keywords)
        ]
        if fallback_candidates:
            return max(fallback_candidates, key=len)[:300]

        return None

    def _extract_reference_author_surnames(self, text: str) -> set[str]:
        if not text:
            return set()

        head = text
        year_match = re.search(r"\b(?:19|20)\d{2}\b", text)
        if year_match:
            head = text[:year_match.start()]

        normalized_head = re.sub(r"\bet\s+al\.?\b", "", head, flags=re.IGNORECASE)
        normalized_head = re.sub(r"\s+(?:and|&)\s+", ", ", normalized_head, flags=re.IGNORECASE)
        normalized_head = normalized_head.strip(" .;:-")

        stop_tokens = {"and", "et", "al", "van", "de", "von", "der", "le"}
        surnames: set[str] = set()

        comma_style_matches = re.findall(
            r"\b([A-Za-z][A-Za-z'\-]{1,})\s*,\s*(?:[A-Za-z]\.\s*){1,3}",
            normalized_head,
        )
        for surname in comma_style_matches:
            lowered = surname.lower()
            if lowered not in stop_tokens:
                surnames.add(lowered)

        name_parts = [part.strip() for part in normalized_head.split(",") if part.strip()]
        for part in name_parts:
            tokens = re.findall(r"[A-Za-z][A-Za-z'\-]+", part)
            if not tokens:
                continue

            filtered_tokens = [
                token.lower()
                for token in tokens
                if len(token) > 1 and token.lower() not in stop_tokens
            ]
            if not filtered_tokens:
                continue

            surnames.add(filtered_tokens[-1])

        return surnames

    def _extract_surnames_from_author_year(self, text: str) -> set[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z'\-]+", text or "")
        surnames = {
            token.lower()
            for token in tokens
            if len(token) > 2 and token.lower() not in {"and", "et", "al"}
        }
        return surnames

    def _extract_author_surnames(self, authors_json: Any) -> set[str]:
        if not isinstance(authors_json, list):
            return set()

        surnames: set[str] = set()
        for item in authors_json:
            if isinstance(item, dict):
                name = str(item.get("name") or "")
            else:
                name = str(item)

            tokens = re.findall(r"[A-Za-z][A-Za-z'\-]+", name)
            if not tokens:
                continue

            surname = tokens[-1].lower()
            if len(surname) > 1:
                surnames.add(surname)

        return surnames

    def _author_year_match(self, entry: ReferenceEntry, target: TargetDocumentInfo) -> float:
        year_match = 1.0 if entry.year and target.publication_year == entry.year else 0.0
        surname_overlap = self._surname_overlap(entry.author_surnames, target.author_surnames)

        if year_match > 0 and surname_overlap > 0:
            return self._clip01((0.60 * year_match) + (0.40 * surname_overlap))
        if year_match > 0:
            return 0.70
        if surname_overlap > 0:
            return 0.40 * surname_overlap
        return 0.0

    def _surname_overlap(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0

        intersection = left & right
        return len(intersection) / max(1, len(left))

    def _semantic_similarity(self, left: str, right: str) -> float:
        left_norm = self._normalize_text(left)
        right_norm = self._normalize_text(right)

        if not left_norm or not right_norm:
            return 0.0

        left_tokens = set(self._tokenize(left_norm))
        right_tokens = set(self._tokenize(right_norm))

        if not left_tokens or not right_tokens:
            return 0.0

        token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        seq_score = SequenceMatcher(None, left_norm[:500], right_norm[:500]).ratio()

        return self._clip01((0.70 * token_score) + (0.30 * seq_score))

    def _title_similarity(self, left: str, right: str) -> float:
        left_norm = self._normalize_title(left)
        right_norm = self._normalize_title(right)

        if not left_norm or not right_norm:
            return 0.0

        left_tokens = set(left_norm.split())
        right_tokens = set(right_norm.split())

        if not left_tokens or not right_tokens:
            return 0.0

        token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        seq_score = SequenceMatcher(None, left_norm, right_norm).ratio()

        return self._clip01((0.60 * seq_score) + (0.40 * token_score))

    def _normalize_title(self, title: str | None) -> str:
        if not title:
            return ""

        normalized = title.lower().strip()
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _normalize_text(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()

    def _tokenize(self, text: str | None) -> list[str]:
        tokens = [token.lower() for token in TOKEN_REGEX.findall(text or "")]
        return [token for token in tokens if token not in STOP_WORDS and len(token) > 2]

    def _clip01(self, value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value

    def _to_decimal(self, value: float) -> Decimal:
        clipped = self._clip01(float(value))
        return Decimal(str(clipped)).quantize(DECIMAL_STEP, rounding=ROUND_HALF_UP)
