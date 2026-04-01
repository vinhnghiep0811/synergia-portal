import json
import logging
import os
import threading
import time
from difflib import SequenceMatcher
from typing import Any
import httpx
from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord

logger = logging.getLogger(__name__)

SS_API_BASE = "https://api.semanticscholar.org/graph/v1"
SS_LOG_BODY_MAX_CHARS = 4000
SS_MAX_ATTEMPTS = max(1, int(os.getenv("SEMANTIC_SCHOLAR_MAX_ATTEMPTS", "1")))
SS_RETRY_DELAY_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_RETRY_DELAY_SECONDS", "60")))
SS_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
SS_MIN_INTERVAL_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS", "1.05")))

SS_FIELDS = "title,authors,year,venue,abstract,externalIds"
TITLE_MATCH_THRESHOLD = 0.82

_ss_rate_lock = threading.Lock()
_last_ss_request_ts = 0.0


class SemanticScholarService:
    def __init__(self, db: Session):
        self.db = db

    def run_for_canonical_document(self, canonical: CanonicalDocument) -> str:
        if not SS_API_KEY:
            logger.warning(
                "[SS enrich] SEMANTIC_SCHOLAR_API_KEY is not set; requests may be heavily rate-limited."
            )

        if canonical.enrichment_status == "enriched":
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
                match_type = "matched_by_doi"

        if paper_data is None and canonical.title_candidate:
            paper_data, title_rate_limited = self._search_by_title(canonical.title_candidate)
            is_rate_limited = is_rate_limited or title_rate_limited
            if paper_data:
                match_type = "matched_by_title"

        if paper_data and match_type:
            self._apply_ss_data(canonical, paper_data, match_type)
            self._sync_title_to_papers(canonical, paper_data.get("title"))
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.info("[SS enrich] Enriched: %s via %s", canonical.id, match_type)
            return "enriched"

        if is_rate_limited:
            canonical.enrichment_status = "rate_limited"
            canonical.match_status = "rate_limited"
            canonical.metadata_source = "semantic_scholar"
            self.db.add(canonical)
            self.db.commit()
            self.db.refresh(canonical)
            logger.info(
                "[SS enrich] Rate limited after %s attempts. Please retry after 5 minutes: %s",
                SS_MAX_ATTEMPTS,
                canonical.id,
            )
            return "rate_limited"

        canonical.enrichment_status = "unmatched"
        canonical.match_status = "unmatched"
        self.db.add(canonical)
        self.db.commit()
        self.db.refresh(canonical)
        logger.info("[SS enrich] Unmatched: %s", canonical.id)
        return "unmatched"

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
            bool(SS_API_KEY),
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
        if not SS_API_KEY:
            return {}
        return {"x-api-key": SS_API_KEY}

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
        headers = self._ss_headers()

        for attempt in range(SS_MAX_ATTEMPTS):
            try:
                self._wait_for_rate_slot()
                self._log_ss_request("GET", url, params, attempt + 1)
                resp = httpx.get(url, params=params, headers=headers, timeout=15)
                self._log_ss_response("GET", str(resp.request.url), resp.status_code, resp.text)

                if resp.status_code == 200:
                    return resp.json(), False
                if resp.status_code == 404:
                    logger.info("[SS] DOI not found: %s", doi)
                    return None, False
                if resp.status_code == 429:
                    if attempt < SS_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "[SS] Rate limited for DOI %s, waiting %ss before retry (%s/%s)",
                            doi,
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            SS_MAX_ATTEMPTS,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning("[SS] Exhausted retries for DOI %s", doi)
                    return None, True
                if 500 <= resp.status_code < 600:
                    if attempt < SS_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "[SS] Server error status=%s for DOI %s, waiting %ss before retry (%s/%s)",
                            resp.status_code,
                            doi,
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            SS_MAX_ATTEMPTS,
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
                if attempt < SS_MAX_ATTEMPTS - 1:
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
        headers = self._ss_headers()

        for attempt in range(SS_MAX_ATTEMPTS):
            try:
                self._wait_for_rate_slot()
                self._log_ss_request("GET", url, params, attempt + 1)
                resp = httpx.get(url, params=params, headers=headers, timeout=15)
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
                            TITLE_MATCH_THRESHOLD,
                            paper.get("paperId"),
                            self._truncate(ss_title, 220),
                        )
                        if score > best_score:
                            best_score = score
                            best_paper = paper

                    logger.info(
                        "[SS SEARCH BEST] best_score=%.4f threshold=%.2f best_paper_id=%s best_title=%s",
                        best_score,
                        TITLE_MATCH_THRESHOLD,
                        (best_paper or {}).get("paperId"),
                        self._truncate((best_paper or {}).get("title", ""), 220),
                    )

                    if best_score >= TITLE_MATCH_THRESHOLD:
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

                if resp.status_code == 429:
                    if attempt < SS_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "[SS] Rate limited for title query '%s', waiting %ss before retry (%s/%s)",
                            title[:60],
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            SS_MAX_ATTEMPTS,
                        )
                        time.sleep(SS_RETRY_DELAY_SECONDS)
                        continue
                    logger.warning("[SS] Exhausted retries for title query '%s'", title[:60])
                    return None, True

                if 500 <= resp.status_code < 600:
                    if attempt < SS_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "[SS] Server error status=%s for title query '%s', waiting %ss before retry (%s/%s)",
                            resp.status_code,
                            title[:60],
                            SS_RETRY_DELAY_SECONDS,
                            attempt + 1,
                            SS_MAX_ATTEMPTS,
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
                if attempt < SS_MAX_ATTEMPTS - 1:
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
        canonical.ss_match_confidence = 1.0 if match_type == "matched_by_doi" else paper_data.get("_match_score", 0.0)
        canonical.metadata_source = "semantic_scholar"
        canonical.enrichment_status = "enriched"
        canonical.match_status = match_type