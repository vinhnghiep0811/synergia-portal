import json
import logging
import os
import threading
import time
from difflib import SequenceMatcher
from typing import Any

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.services.crossref_service import CrossrefService
from app.services.runtime_config_service import RuntimeConfigService


logger = logging.getLogger(__name__)

SS_API_BASE = "https://api.semanticscholar.org/graph/v1"
SS_LOG_BODY_MAX_CHARS = 4000
SS_MAX_ATTEMPTS_DEFAULT = max(1, int(os.getenv("SEMANTIC_SCHOLAR_MAX_ATTEMPTS", "1")))
SS_RETRY_DELAY_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_RETRY_DELAY_SECONDS", "60")))
SS_API_KEY_DEFAULT = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
SS_REQUEST_TIMEOUT_SECONDS_DEFAULT = max(
    1.0,
    float(os.getenv("SEMANTIC_SCHOLAR_TIMEOUT_SECONDS", "15")),
)
SS_MIN_INTERVAL_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS", "1.05")))

SS_FIELDS = "title,authors,year,venue,abstract,externalIds"
TITLE_MATCH_THRESHOLD_DEFAULT = 0.82
DOI_TITLE_MISMATCH_THRESHOLD = 0.60
CROSSREF_FALLBACK_MATCH_STATUSES = {"verified", "partial", "weak"}

_ss_rate_lock = threading.Lock()
_last_ss_request_ts = 0.0


class SemanticScholarService:
    def __init__(self, db: Session):
        self.db = db
        runtime_config = RuntimeConfigService.get(db)
        self.env_api_key = SS_API_KEY_DEFAULT or None
        configured_api_key = (runtime_config.semantic_scholar_api_key or "").strip() or None
        self.api_key = configured_api_key or self.env_api_key
        self.max_attempts = max(1, int(runtime_config.pipeline_retry_limit or SS_MAX_ATTEMPTS_DEFAULT))
        self.request_timeout_seconds = max(
            1.0,
            float(runtime_config.pipeline_timeout_seconds or SS_REQUEST_TIMEOUT_SECONDS_DEFAULT),
        )
        self.title_match_threshold = max(
            0.0,
            min(1.0, float(runtime_config.metadata_match_threshold)),
        )
        self.crossref_service = CrossrefService(
            timeout_seconds=self.request_timeout_seconds,
            title_match_threshold=self.title_match_threshold,
        )

    def _fallback_to_env_key_if_needed(self, status_code: int, context: str) -> bool:
        if status_code not in {401, 403}:
            return False
        if not self.env_api_key:
            return False
        if self.api_key == self.env_api_key:
            return False

        logger.warning(
            "[SS AUTH] Received status=%s for %s. Falling back to .env SEMANTIC_SCHOLAR_API_KEY.",
            status_code,
            context,
        )
        self.api_key = self.env_api_key
        return True

    def run_for_canonical_document(self, canonical: CanonicalDocument) -> str:
        if not self.api_key:
            logger.warning(
                "[SS enrich] SEMANTIC_SCHOLAR_API_KEY is not set; requests may be heavily rate-limited."
            )

        if canonical.enrichment_status == "enriched":
            # Attempt to heal any missing fields from already-saved Crossref verification data
            if canonical.crossref_verification_json:
                self._apply_crossref_verification(canonical, canonical.crossref_verification_json)
                self.db.add(canonical)
                self.db.commit()
            logger.info("[SS enrich] Already enriched, skipping: %s", canonical.id)
            return "skipped_already_enriched"

        logger.info(
            "[SS enrich] Start enriching canonical_id=%s, doi=%s",
            canonical.id,
            canonical.doi,
        )

        paper_data = None
        match_type = None
        is_rate_limited = False

        if canonical.doi:
            paper_data, is_rate_limited = self._get_by_doi(canonical.doi)
            if paper_data:
                if self._is_doi_title_mismatch(canonical, paper_data):
                    canonical = self._fallback_canonical_to_fingerprint(canonical)
                    paper_data = None
                else:
                    match_type = "matched_by_doi"

        if paper_data is None and canonical.title_candidate:
            paper_data, title_rate_limited = self._search_by_title(canonical.title_candidate)
            is_rate_limited = is_rate_limited or title_rate_limited
            if paper_data:
                match_type = "matched_by_title"

        if paper_data and match_type:
            self._apply_ss_data(canonical, paper_data, match_type)
            self._apply_crossref_verification(
                canonical,
                self._verify_with_crossref(canonical, paper_data),
            )
            self._sync_title_to_papers(canonical, paper_data.get("title"))
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.info("[SS enrich] Enriched: %s via %s", canonical.id, match_type)
            return "enriched"

        if is_rate_limited:
            self._mark_rate_limited(canonical)
            return "rate_limited"

        crossref_result = self._try_crossref_fallback(canonical)
        if crossref_result == "enriched":
            return "enriched"
        if crossref_result == "rate_limited":
            return "rate_limited"

        self._mark_unmatched(canonical)
        return "unmatched"

    def _mark_rate_limited(self, canonical: CanonicalDocument) -> None:
        canonical.enrichment_status = "rate_limited"
        canonical.match_status = "rate_limited"
        canonical.metadata_source = "semantic_scholar"
        self.db.add(canonical)
        self.db.commit()
        self.db.refresh(canonical)
        logger.info(
            "[SS enrich] Rate limited after %s attempts. Please retry after 5 minutes: %s",
            self.max_attempts,
            canonical.id,
        )

    def _mark_unmatched(self, canonical: CanonicalDocument) -> None:
        canonical.enrichment_status = "unmatched"
        canonical.match_status = "unmatched"
        canonical.metadata_source = "semantic_scholar"
        self.db.add(canonical)
        self.db.commit()
        self.db.refresh(canonical)
        logger.info("[SS enrich] Unmatched: %s", canonical.id)

    def _sync_title_to_papers(self, canonical: CanonicalDocument, ss_title: str | None) -> None:
        if not ss_title:
            return

        papers = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .all()
        )

        for paper in papers:
            if (
                not paper.detected_title
                or paper.detected_title.strip() == ""
                or paper.detected_title == canonical.title_candidate
            ):
                paper.detected_title = ss_title

    def _is_doi_title_mismatch(
        self,
        canonical: CanonicalDocument,
        paper_data: dict[str, Any],
    ) -> bool:
        expected_title = canonical.title_candidate
        ss_title = paper_data.get("title")
        if not expected_title or not ss_title:
            return False

        normalized_expected = self._normalize_title(expected_title)
        if len(normalized_expected.split()) < 3:
            return False

        score = self._title_similarity(expected_title, ss_title)
        if score >= DOI_TITLE_MISMATCH_THRESHOLD:
            return False

        logger.warning(
            "[SS enrich] Rejecting DOI match due to title mismatch: canonical_id=%s doi=%s score=%.4f parsed_title=%s ss_title=%s",
            canonical.id,
            canonical.doi,
            score,
            self._truncate(expected_title, 220),
            self._truncate(ss_title, 220),
        )
        return True

    def _fallback_canonical_to_fingerprint(self, canonical: CanonicalDocument) -> CanonicalDocument:
        papers = (
            self.db.query(PaperRecord)
            .filter(PaperRecord.canonical_document_id == canonical.id)
            .order_by(PaperRecord.created_at.asc())
            .all()
        )
        fingerprint = canonical.fingerprint or next(
            (paper.detected_fingerprint for paper in papers if paper.detected_fingerprint),
            None,
        )

        if not fingerprint:
            canonical.enrichment_status = "unmatched"
            canonical.match_status = "doi_title_mismatch"
            canonical.metadata_source = "semantic_scholar"
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.warning(
                "[SS enrich] DOI mismatch found but no fingerprint is available for canonical_id=%s",
                canonical.id,
            )
            return canonical

        target = (
            self.db.query(CanonicalDocument)
            .filter(
                or_(
                    CanonicalDocument.canonical_key == fingerprint,
                    CanonicalDocument.fingerprint == fingerprint,
                )
            )
            .first()
        )

        for paper in papers:
            paper.detected_doi = None
            paper.detected_fingerprint = paper.detected_fingerprint or fingerprint

        if target and target.id != canonical.id:
            if not target.title_candidate:
                target.title_candidate = canonical.title_candidate
            if not target.fingerprint:
                target.fingerprint = fingerprint

            for paper in papers:
                paper.canonical_document_id = target.id

            canonical.doi = None
            canonical.enrichment_status = "unmatched"
            canonical.match_status = "doi_title_mismatch_superseded"
            canonical.metadata_source = "semantic_scholar"
            self.db.add(target)
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(target)
            logger.info(
                "[SS enrich] Moved papers from rejected DOI canonical_id=%s to fingerprint canonical_id=%s",
                canonical.id,
                target.id,
            )
            return target

        canonical.canonical_key = fingerprint
        canonical.canonical_type = "fingerprint"
        canonical.fingerprint = fingerprint
        canonical.doi = None
        canonical.enrichment_status = "pending"
        canonical.match_status = "doi_title_mismatch"
        canonical.metadata_source = "semantic_scholar"
        self.db.add(canonical)
        self.db.commit()
        self.db.refresh(canonical)
        logger.info(
            "[SS enrich] Re-keyed canonical_id=%s from rejected DOI to fingerprint",
            canonical.id,
        )
        return canonical

    def _truncate(self, text: str, max_chars: int = SS_LOG_BODY_MAX_CHARS) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}...<truncated>"

    def _log_ss_request(self, method: str, url: str, params: dict[str, Any], attempt: int) -> None:
        logger.info(
            "[SS HTTP REQUEST] method=%s url=%s params=%s attempt=%s has_api_key=%s",
            method,
            url,
            json.dumps(params, ensure_ascii=True),
            attempt,
            bool(self.api_key),
        )

    def _log_ss_response(self, method: str, url: str, status_code: int, body_text: str) -> None:
        logger.info(
            "[SS HTTP RESPONSE] method=%s url=%s status=%s body=%s",
            method,
            url,
            status_code,
            self._truncate(body_text),
        )

    def _wait_for_rate_slot(self) -> None:
        global _last_ss_request_ts

        with _ss_rate_lock:
            now = time.monotonic()
            elapsed = now - _last_ss_request_ts
            if elapsed < SS_MIN_INTERVAL_SECONDS:
                wait = SS_MIN_INTERVAL_SECONDS - elapsed
                logger.info(
                    "[SS RATE] Waiting %.2fs to respect min interval %.2fs",
                    wait,
                    SS_MIN_INTERVAL_SECONDS,
                )
                time.sleep(wait)
            _last_ss_request_ts = time.monotonic()

    def _ss_headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"x-api-key": self.api_key}

    def _normalize_title(self, title: str) -> str:
        import re

        title = re.sub(r"([a-z])([A-Z])", r"\1 \2", title)
        title = title.lower().strip()
        title = re.sub(r"[^a-z0-9\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title

    def _title_similarity(self, a: str, b: str) -> float:
        na = self._normalize_title(a)
        nb = self._normalize_title(b)
        if not na or not nb:
            return 0.0
        if na.replace(" ", "") == nb.replace(" ", ""):
            return 1.0

        set_a = set(na.split())
        set_b = set(nb.split())
        token_score = len(set_a & set_b) / len(set_a | set_b) if (set_a and set_b) else 0.0
        seq_score = SequenceMatcher(None, na, nb).ratio()
        return 0.6 * seq_score + 0.4 * token_score

    def _get_by_doi(self, doi: str) -> tuple[dict[str, Any] | None, bool]:
        url = f"{SS_API_BASE}/paper/{doi}"
        params = {"fields": SS_FIELDS}
        effective_max_attempts = self.max_attempts + (
            1 if (self.env_api_key and self.api_key != self.env_api_key) else 0
        )

        for attempt in range(effective_max_attempts):
            try:
                self._wait_for_rate_slot()
                headers = self._ss_headers()
                self._log_ss_request("GET", url, params, attempt + 1)
                resp = httpx.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.request_timeout_seconds,
                )
                self._log_ss_response("GET", str(resp.request.url), resp.status_code, resp.text)

                if resp.status_code == 200:
                    return resp.json(), False
                if resp.status_code == 404:
                    logger.info("[SS] DOI not found: %s", doi)
                    return None, False
                if resp.status_code in {401, 403}:
                    if self._fallback_to_env_key_if_needed(resp.status_code, f"doi={doi}"):
                        continue
                    logger.warning(
                        "[SS AUTH] Unauthorized for DOI %s with current API key. status=%s",
                        doi,
                        resp.status_code,
                    )
                    return None, False
                if resp.status_code == 429:
                    if attempt < effective_max_attempts - 1:
                        logger.warning(
                            "[SS] Rate limited for DOI %s, waiting %ss before retry (%s/%s)",
                            doi,
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            effective_max_attempts,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning("[SS] Exhausted retries for DOI %s", doi)
                    return None, True
                if 500 <= resp.status_code < 600:
                    if attempt < effective_max_attempts - 1:
                        logger.warning(
                            "[SS] Server error status=%s for DOI %s, waiting %ss before retry (%s/%s)",
                            resp.status_code,
                            doi,
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            effective_max_attempts,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning(
                        "[SS] Exhausted retries for DOI %s with last status=%s",
                        doi,
                        resp.status_code,
                    )
                    continue

                logger.warning("[SS] Unexpected status %s for DOI %s", resp.status_code, doi)
                return None, False

            except httpx.RequestError as e:
                logger.warning(
                    "[SS] Request error attempt %s method=GET url=%s params=%s error=%s",
                    attempt + 1,
                    url,
                    json.dumps(params, ensure_ascii=True),
                    e,
                )
                if attempt < effective_max_attempts - 1:
                    time.sleep(SS_RETRY_DELAY_SECONDS)
                else:
                    logger.warning("[SS] Exhausted request-error retries for DOI %s", doi)

        return None, False

    def _search_by_title(self, title: str) -> tuple[dict[str, Any] | None, bool]:
        url = f"{SS_API_BASE}/paper/search"
        params = {
            "query": title,
            "limit": 5,
            "fields": SS_FIELDS,
        }
        effective_max_attempts = self.max_attempts + (
            1 if (self.env_api_key and self.api_key != self.env_api_key) else 0
        )

        for attempt in range(effective_max_attempts):
            try:
                self._wait_for_rate_slot()
                headers = self._ss_headers()
                self._log_ss_request("GET", url, params, attempt + 1)
                resp = httpx.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.request_timeout_seconds,
                )
                self._log_ss_response("GET", str(resp.request.url), resp.status_code, resp.text)

                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("data", [])
                    logger.info(
                        "[SS SEARCH] query_title=%s returned_results=%s",
                        self._truncate(title, 200),
                        len(results),
                    )
                    if not results:
                        return None, False

                    best_paper = None
                    best_score = 0.0
                    for idx, paper in enumerate(results, start=1):
                        ss_title = paper.get("title", "")
                        score = self._title_similarity(title, ss_title)
                        logger.info(
                            "[SS SEARCH CANDIDATE] rank=%s score=%.4f threshold=%.2f paper_id=%s title=%s",
                            idx,
                            score,
                            self.title_match_threshold,
                            paper.get("paperId"),
                            self._truncate(ss_title, 220),
                        )
                        if score > best_score:
                            best_score = score
                            best_paper = paper

                    logger.info(
                        "[SS SEARCH BEST] best_score=%.4f threshold=%.2f best_paper_id=%s best_title=%s",
                        best_score,
                        self.title_match_threshold,
                        (best_paper or {}).get("paperId"),
                        self._truncate((best_paper or {}).get("title", ""), 220),
                    )

                    if best_score >= self.title_match_threshold:
                        best_paper["_match_score"] = best_score
                        logger.info(
                            "[SS] Title match: score=%.2f query='%s' matched='%s'",
                            best_score,
                            title[:60],
                            best_paper.get("title", "")[:60],
                        )
                        return best_paper, False

                    logger.info(
                        "[SS] No confident match: best_score=%.2f for '%s'",
                        best_score,
                        title[:60],
                    )
                    return None, False

                if resp.status_code in {401, 403}:
                    if self._fallback_to_env_key_if_needed(resp.status_code, f"title={title[:60]}"):
                        continue
                    logger.warning(
                        "[SS AUTH] Unauthorized for title query '%s' with current API key. status=%s",
                        title[:60],
                        resp.status_code,
                    )
                    return None, False

                if resp.status_code == 429:
                    if attempt < effective_max_attempts - 1:
                        logger.warning(
                            "[SS] Rate limited for title query '%s', waiting %ss before retry (%s/%s)",
                            title[:60],
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            effective_max_attempts,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning("[SS] Exhausted retries for title query '%s'", title[:60])
                    return None, True

                if 500 <= resp.status_code < 600:
                    if attempt < effective_max_attempts - 1:
                        logger.warning(
                            "[SS] Server error status=%s for title query '%s', waiting %ss before retry (%s/%s)",
                            resp.status_code,
                            title[:60],
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            effective_max_attempts,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning(
                        "[SS] Exhausted retries for title query '%s' with last status=%s",
                        title[:60],
                        resp.status_code,
                    )
                    continue

                logger.warning("[SS] Search status %s for title '%s'", resp.status_code, title[:60])
                return None, False

            except httpx.RequestError as e:
                logger.warning(
                    "[SS] Request error attempt %s method=GET url=%s params=%s error=%s",
                    attempt + 1,
                    url,
                    json.dumps(params, ensure_ascii=True),
                    e,
                )
                if attempt < effective_max_attempts - 1:
                    time.sleep(SS_RETRY_DELAY_SECONDS)
                else:
                    logger.warning(
                        "[SS] Exhausted request-error retries for title query '%s'",
                        title[:60],
                    )

        return None, False

    def _apply_ss_data(self, canonical: CanonicalDocument, paper_data: dict[str, Any], match_type: str) -> None:
        canonical.title = paper_data.get("title") or canonical.title_candidate
        canonical.publication_year = paper_data.get("year")
        canonical.venue = paper_data.get("venue")
        canonical.abstract = paper_data.get("abstract")
        canonical.authors_json = [
            {"name": a.get("name", ""), "author_id": a.get("authorId")}
            for a in paper_data.get("authors", [])
        ]
        canonical.ss_paper_id = paper_data.get("paperId")
        canonical.ss_match_confidence = (
            1.0 if match_type == "matched_by_doi" else paper_data.get("_match_score", 0.0)
        )
        canonical.metadata_source = "semantic_scholar"
        canonical.enrichment_status = "enriched"
        canonical.match_status = match_type

    def _try_crossref_fallback(self, canonical: CanonicalDocument) -> str:
        verification = self._verify_canonical_candidate_with_crossref(canonical)

        if (
            verification.get("status") == "conflict"
            and canonical.doi
            and (canonical.title_candidate or canonical.title)
        ):
            title_only_verification = self._verify_canonical_candidate_with_crossref(
                canonical,
                title_only=True,
            )
            if (
                self._is_crossref_fallback_match(title_only_verification)
                or title_only_verification.get("status") in {"rate_limited", "error"}
            ):
                verification = title_only_verification

        if self._is_crossref_fallback_match(verification):
            crossref_metadata = verification.get("crossref_metadata") or {}
            match_type = self._crossref_match_type(verification)
            self._apply_crossref_data(
                canonical,
                crossref_metadata,
                match_type,
                verification,
            )
            self._sync_title_to_papers(canonical, canonical.title)
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.info(
                "[Crossref fallback] Enriched canonical_id=%s via %s",
                canonical.id,
                match_type,
            )
            return "enriched"

        self._apply_crossref_verification(canonical, verification)
        if verification.get("status") == "rate_limited":
            canonical.enrichment_status = "rate_limited"
            canonical.match_status = "crossref_rate_limited"
            canonical.metadata_source = "crossref"
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.info("[Crossref fallback] Rate limited canonical_id=%s", canonical.id)
            return "rate_limited"

        logger.info(
            "[Crossref fallback] No matched metadata canonical_id=%s status=%s",
            canonical.id,
            verification.get("status"),
        )
        return "unmatched"

    def _verify_canonical_candidate_with_crossref(
        self,
        canonical: CanonicalDocument,
        *,
        title_only: bool = False,
    ) -> dict[str, Any]:
        primary_metadata = self._canonical_primary_metadata(canonical)
        if title_only:
            primary_metadata = {**primary_metadata, "doi": None}

        try:
            verification = self.crossref_service.verify_metadata(
                primary_metadata,
                lookup_doi=None if title_only else primary_metadata.get("doi"),
                lookup_title=primary_metadata.get("title"),
            )
            logger.info(
                "[Crossref fallback] canonical_id=%s status=%s confidence=%s title_only=%s",
                canonical.id,
                verification.get("status"),
                verification.get("confidence"),
                title_only,
            )
            return verification
        except Exception as exc:
            logger.warning(
                "[Crossref fallback] Failed canonical_id=%s error=%s",
                canonical.id,
                exc,
            )
            return {
                "provider": "crossref",
                "status": "error",
                "queried_by": "title" if title_only else "unknown",
                "confidence": 0.0,
                "conflicts": [],
                "fields": {},
                "primary_metadata": primary_metadata,
                "crossref_metadata": None,
                "error": str(exc),
            }

    def _canonical_primary_metadata(self, canonical: CanonicalDocument) -> dict[str, Any]:
        return {
            "source": "parsed_pdf",
            "doi": canonical.doi,
            "title": canonical.title_candidate or canonical.title,
            "authors": [],
            "year": None,
            "venue": None,
            "abstract": None,
        }

    def _is_crossref_fallback_match(self, verification: dict[str, Any]) -> bool:
        return (
            verification.get("status") in CROSSREF_FALLBACK_MATCH_STATUSES
            and bool(verification.get("crossref_metadata"))
        )

    def _crossref_match_type(self, verification: dict[str, Any]) -> str:
        queried_by = verification.get("queried_by")
        if queried_by == "doi":
            return "matched_by_crossref_doi"
        if queried_by == "title":
            return "matched_by_crossref_title"
        return "matched_by_crossref"

    def _apply_crossref_data(
        self,
        canonical: CanonicalDocument,
        crossref_metadata: dict[str, Any],
        match_type: str,
        verification: dict[str, Any],
    ) -> None:
        canonical.title = crossref_metadata.get("title") or canonical.title_candidate
        canonical.publication_year = crossref_metadata.get("year")
        canonical.venue = crossref_metadata.get("venue")
        canonical.abstract = crossref_metadata.get("abstract")
        canonical.authors_json = [
            {"name": name, "author_id": None}
            for name in crossref_metadata.get("authors", [])
            if name
        ]
        self._set_crossref_doi_if_available(canonical, crossref_metadata.get("doi"))
        canonical.ss_paper_id = None
        canonical.ss_match_confidence = None
        canonical.metadata_source = "crossref"
        canonical.enrichment_status = "enriched"
        canonical.match_status = match_type
        self._apply_crossref_verification(canonical, verification)

    def _set_crossref_doi_if_available(
        self,
        canonical: CanonicalDocument,
        doi: str | None,
    ) -> None:
        normalized_doi = str(doi).strip().lower() if doi else None
        if not normalized_doi or canonical.doi:
            return

        existing = (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.doi == normalized_doi)
            .first()
        )
        if existing and existing.id != canonical.id:
            logger.warning(
                "[Crossref fallback] Skipping DOI assignment canonical_id=%s doi=%s owner_id=%s",
                canonical.id,
                normalized_doi,
                existing.id,
            )
            return

        canonical.doi = normalized_doi

    def _verify_with_crossref(
        self,
        canonical: CanonicalDocument,
        paper_data: dict[str, Any],
    ) -> dict[str, Any]:
        primary_metadata = self._semantic_scholar_primary_metadata(canonical, paper_data)
        try:
            verification = self.crossref_service.verify_metadata(
                primary_metadata,
                lookup_doi=primary_metadata.get("doi"),
                lookup_title=primary_metadata.get("title") or canonical.title_candidate,
            )
            logger.info(
                "[Crossref verify] canonical_id=%s status=%s confidence=%s",
                canonical.id,
                verification.get("status"),
                verification.get("confidence"),
            )
            return verification
        except Exception as exc:
            logger.warning(
                "[Crossref verify] Failed canonical_id=%s error=%s",
                canonical.id,
                exc,
            )
            return {
                "provider": "crossref",
                "status": "error",
                "queried_by": "unknown",
                "confidence": 0.0,
                "conflicts": [],
                "fields": {},
                "primary_metadata": primary_metadata,
                "crossref_metadata": None,
                "error": str(exc),
            }

    def _semantic_scholar_primary_metadata(
        self,
        canonical: CanonicalDocument,
        paper_data: dict[str, Any],
    ) -> dict[str, Any]:
        external_ids = paper_data.get("externalIds") or {}
        authors = [
            a.get("name", "")
            for a in paper_data.get("authors", [])
            if a.get("name")
        ]
        return {
            "source": "semantic_scholar",
            "doi": canonical.doi or external_ids.get("DOI"),
            "title": paper_data.get("title") or canonical.title or canonical.title_candidate,
            "authors": authors,
            "year": paper_data.get("year") or canonical.publication_year,
            "venue": paper_data.get("venue") or canonical.venue,
            "abstract": paper_data.get("abstract") or canonical.abstract,
            "external_ids": external_ids,
        }

    def _apply_crossref_verification(
        self,
        canonical: CanonicalDocument,
        verification: dict[str, Any],
    ) -> None:
        canonical.crossref_match_status = verification.get("status")
        confidence = verification.get("confidence")
        canonical.crossref_match_confidence = confidence if confidence is not None else None
        canonical.crossref_metadata_json = verification.get("crossref_metadata")
        canonical.crossref_verification_json = verification

        # If Crossref verification was successful/matched, replace missing primary fields with Crossref values
        if verification.get("status") in {"verified", "partial", "weak"}:
            fields_comparison = verification.get("fields", {})

            # 1. venue
            venue_cmp = fields_comparison.get("venue", {})
            if venue_cmp.get("status") == "missing" and not venue_cmp.get("primary") and venue_cmp.get("crossref"):
                canonical.venue = venue_cmp.get("crossref")
                logger.info(
                    "[Crossref verify] Replaced missing venue with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.venue,
                )

            # 2. publication_year
            year_cmp = fields_comparison.get("year", {})
            if year_cmp.get("status") == "missing" and not year_cmp.get("primary") and year_cmp.get("crossref"):
                canonical.publication_year = year_cmp.get("crossref")
                logger.info(
                    "[Crossref verify] Replaced missing publication_year with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.publication_year,
                )

            # 3. abstract
            abstract_cmp = fields_comparison.get("abstract", {})
            if abstract_cmp.get("status") == "missing" and not abstract_cmp.get("primary") and abstract_cmp.get("crossref"):
                canonical.abstract = abstract_cmp.get("crossref")
                logger.info(
                    "[Crossref verify] Replaced missing abstract with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.abstract[:100] if canonical.abstract else "",
                )

            # 4. authors_json
            authors_cmp = fields_comparison.get("authors", {})
            if authors_cmp.get("status") == "missing" and not authors_cmp.get("primary") and authors_cmp.get("crossref"):
                canonical.authors_json = [
                    {"name": name, "author_id": None}
                    for name in authors_cmp.get("crossref", [])
                    if name
                ]
                logger.info(
                    "[Crossref verify] Replaced missing authors with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.authors_json,
                )

            # 5. title
            title_cmp = fields_comparison.get("title", {})
            if title_cmp.get("status") == "missing" and not title_cmp.get("primary") and title_cmp.get("crossref"):
                canonical.title = title_cmp.get("crossref")
                logger.info(
                    "[Crossref verify] Replaced missing title with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.title,
                )

            # 6. doi
            doi_cmp = fields_comparison.get("doi", {})
            if doi_cmp.get("status") == "missing" and not doi_cmp.get("primary") and doi_cmp.get("crossref"):
                self._set_crossref_doi_if_available(canonical, doi_cmp.get("crossref"))
                logger.info(
                    "[Crossref verify] Replaced missing DOI with Crossref value for canonical_id=%s: %s",
                    canonical.id,
                    canonical.doi,
                )
