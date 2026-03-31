import logging
import json
import os
import sys
import threading
import time
from uuid import UUID
from difflib import SequenceMatcher
import httpx

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord

logger = logging.getLogger(__name__)

SS_API_BASE = "https://api.semanticscholar.org/graph/v1"
SS_LOG_BODY_MAX_CHARS = 4000
SS_MAX_ATTEMPTS = max(1, int(os.getenv("SEMANTIC_SCHOLAR_MAX_ATTEMPTS", "1")))
SS_RETRY_DELAY_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_RETRY_DELAY_SECONDS", "60")))
SS_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
SS_MIN_INTERVAL_SECONDS = max(1.0, float(os.getenv("SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS", "1.05")))

_ss_rate_lock = threading.Lock()
_last_ss_request_ts = 0.0

# Cac truong can lay tu Semantic Scholar
SS_FIELDS = "title,authors,year,venue,abstract,externalIds"

# Nguong similarity de chap nhan match khi tim qua title (0.0 - 1.0)
TITLE_MATCH_THRESHOLD = 0.82

def _sync_title_to_papers(db, canonical: CanonicalDocument, ss_title: str) -> None:
    """
    Đồng bộ title chuẩn từ Semantic Scholar xuống các PaperRecord
    đang trỏ tới canonical này.
    """
    if not ss_title:
        return

    papers = (
        db.query(PaperRecord)
        .filter(PaperRecord.canonical_document_id == canonical.id)
        .all()
    )

    for paper in papers:
        # chỉ ghi đè khi paper chưa có title hoặc đang giữ title detect tạm
        if not paper.detected_title or paper.detected_title.strip() == "" or paper.detected_title == canonical.title_candidate:
            paper.detected_title = ss_title

def _truncate(text: str, max_chars: int = SS_LOG_BODY_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...<truncated>"


def _log_ss_request(method: str, url: str, params: dict, attempt: int) -> None:
    logger.info(
        "[SS HTTP REQUEST] method=%s url=%s params=%s attempt=%s has_api_key=%s",
        method,
        url,
        json.dumps(params, ensure_ascii=True),
        attempt,
        bool(SS_API_KEY),
    )


def _log_ss_response(method: str, url: str, status_code: int, body_text: str) -> None:
    logger.info(
        "[SS HTTP RESPONSE] method=%s url=%s status=%s body=%s",
        method,
        url,
        status_code,
        _truncate(body_text),
    )


def _wait_for_rate_slot() -> None:
    """Enforce minimum gap between Semantic Scholar requests in this worker process."""
    global _last_ss_request_ts

    with _ss_rate_lock:
        now = time.monotonic()
        elapsed = now - _last_ss_request_ts
        if elapsed < SS_MIN_INTERVAL_SECONDS:
            wait = SS_MIN_INTERVAL_SECONDS - elapsed
            logger.info("[SS RATE] Waiting %.2fs to respect min interval %.2fs", wait, SS_MIN_INTERVAL_SECONDS)
            time.sleep(wait)
        _last_ss_request_ts = time.monotonic()


def _ss_headers() -> dict:
    if not SS_API_KEY:
        return {}
    return {"x-api-key": SS_API_KEY}


# -------------------------------------------------------
# Helper: tinh similarity don gian giua 2 chuoi khong can thu vien
# -------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Chuyen ve lowercase, bo dau cau de so sanh."""
    import re
    title = re.sub(r"([a-z])([A-Z])", r"\1 \2", title)
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def _title_similarity(a: str, b: str) -> float:
    """
    Tinh he so Jaccard similarity giua 2 chuoi dua tren tap tu.
    Khong can thu vien ngoai, du dung cho viec so sanh title paper.
    """
    na = _normalize_title(a)
    nb = _normalize_title(b)
    if not na or not nb:
        return 0.0
    if na.replace(" ", "") == nb.replace(" ", ""):
        return 1.0
    set_a = set(na.split())
    set_b = set(nb.split())
    
    token_score = len(set_a & set_b) / len(set_a | set_b) if (set_a and set_b) else 0.0
    seq_score = SequenceMatcher(None, na, nb).ratio()

    return 0.6 * seq_score + 0.4 * token_score


# -------------------------------------------------------
# Helper: goi Semantic Scholar, co retry don gian
# -------------------------------------------------------

def _get_by_doi(doi: str) -> tuple[dict | None, bool]:
    """
    Goi truc tiep theo DOI.
    Tra ve (paper_data, is_rate_limited_exhausted).
    """
    url = f"{SS_API_BASE}/paper/{doi}"
    params = {"fields": SS_FIELDS}
    headers = _ss_headers()

    for attempt in range(SS_MAX_ATTEMPTS):
        try:
            _wait_for_rate_slot()
            _log_ss_request("GET", url, params, attempt + 1)
            resp = httpx.get(url, params=params, headers=headers, timeout=15)
            _log_ss_response("GET", str(resp.request.url), resp.status_code, resp.text)
            if resp.status_code == 200:
                return resp.json(), False
            if resp.status_code == 404:
                logger.info(f"[SS] DOI not found: {doi}")
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
                logger.warning("[SS] Exhausted retries for DOI %s with last status=%s", doi, resp.status_code)
                continue
            logger.warning(f"[SS] Unexpected status {resp.status_code} for DOI {doi}")
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


def _search_by_title(title: str) -> tuple[dict | None, bool]:
    """
    Tim kiem theo title, lay ket qua dau tien co similarity >= nguong.
    Tra ve (paper_data, is_rate_limited_exhausted).
    """
    url = f"{SS_API_BASE}/paper/search"
    params = {
        "query": title,
        "limit": 5,
        "fields": SS_FIELDS,
    }
    headers = _ss_headers()

    for attempt in range(SS_MAX_ATTEMPTS):
        try:
            _wait_for_rate_slot()
            _log_ss_request("GET", url, params, attempt + 1)
            resp = httpx.get(url, params=params, headers=headers, timeout=15)
            _log_ss_response("GET", str(resp.request.url), resp.status_code, resp.text)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", [])
                logger.info(
                    "[SS SEARCH] query_title=%s returned_results=%s",
                    _truncate(title, 200),
                    len(results),
                )
                if not results:
                    return None, False

                # So sanh similarity voi tung ket qua, lay cai tot nhat
                best_paper = None
                best_score = 0.0
                for idx, paper in enumerate(results, start=1):
                    ss_title = paper.get("title", "")
                    score = _title_similarity(title, ss_title)
                    logger.info(
                        "[SS SEARCH CANDIDATE] rank=%s score=%.4f threshold=%.2f paper_id=%s title=%s",
                        idx,
                        score,
                        TITLE_MATCH_THRESHOLD,
                        paper.get("paperId"),
                        _truncate(ss_title, 220),
                    )
                    if score > best_score:
                        best_score = score
                        best_paper = paper

                logger.info(
                    "[SS SEARCH BEST] best_score=%.4f threshold=%.2f best_paper_id=%s best_title=%s",
                    best_score,
                    TITLE_MATCH_THRESHOLD,
                    (best_paper or {}).get("paperId"),
                    _truncate((best_paper or {}).get("title", ""), 220),
                )

                if best_score >= TITLE_MATCH_THRESHOLD:
                    logger.info(
                        f"[SS] Title match: score={best_score:.2f} "
                        f"query='{title[:60]}' matched='{best_paper.get('title', '')[:60]}'"
                    )
                    # Gan score vao de luu vao DB
                    best_paper["_match_score"] = best_score
                    return best_paper, False
                else:
                    logger.info(
                        f"[SS] No confident match: best_score={best_score:.2f} for '{title[:60]}'"
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

            logger.warning(f"[SS] Search status {resp.status_code} for title '{title[:60]}'")
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
                logger.warning("[SS] Exhausted request-error retries for title query '%s'", title[:60])

    return None, False


# -------------------------------------------------------
# Helper: map du lieu tu Semantic Scholar vao CanonicalDocument
# -------------------------------------------------------

def _apply_ss_data(canonical: CanonicalDocument, paper_data: dict, match_type: str) -> None:
    """Dien du lieu tu Semantic Scholar vao cac truong cua CanonicalDocument."""
    canonical.title = paper_data.get("title") or canonical.title_candidate
    canonical.publication_year = paper_data.get("year")
    canonical.venue = paper_data.get("venue")
    canonical.abstract = paper_data.get("abstract")

    # Authors: Semantic Scholar tra ve list {"authorId": ..., "name": ...}
    authors = paper_data.get("authors", [])
    canonical.authors_json = [
        {"name": a.get("name", ""), "author_id": a.get("authorId")}
        for a in authors
    ]

    # Semantic Scholar paper ID
    canonical.ss_paper_id = paper_data.get("paperId")

    # Match confidence
    if match_type == "matched_by_doi":
        canonical.ss_match_confidence = 1.0
    else:
        canonical.ss_match_confidence = paper_data.get("_match_score", 0.0)

    canonical.metadata_source = "semantic_scholar"
    canonical.enrichment_status = "enriched"
    canonical.match_status = match_type


# -------------------------------------------------------
# Task chinh: duoc goi boi RQ worker
# -------------------------------------------------------

def semantic_scholar_enrich(canonical_document_id: str) -> None:
    """
    Task RQ: goi Semantic Scholar de enrich CanonicalDocument.
    Duoc enqueue tu pdf_parse sau khi canonicalize xong.
    """
    db = SessionLocal()

    try:
        cid = UUID(canonical_document_id)
    except ValueError:
        logger.error(f"[SS enrich] Invalid canonical_document_id: {canonical_document_id}")
        return

    try:
        canonical = (
            db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == cid)
            .first()
        )

        if not canonical:
            logger.error(f"[SS enrich] CanonicalDocument not found: {cid}")
            return

        if not SS_API_KEY:
            logger.warning("[SS enrich] SEMANTIC_SCHOLAR_API_KEY is not set; requests may be heavily rate-limited.")

        # Neu da duoc enrich roi thi bo qua (canonical caching)
        if canonical.enrichment_status == "enriched":
            logger.info(f"[SS enrich] Already enriched, skipping: {cid}")
            return

        logger.info(f"[SS enrich] Start enriching canonical_id={cid}, doi={canonical.doi}")

        paper_data = None
        match_type = None
        is_rate_limited = False

        # Uu tien DOI
        if canonical.doi:
            paper_data, is_rate_limited = _get_by_doi(canonical.doi)
            if paper_data:
                match_type = "matched_by_doi"

        # Fallback: tim theo title_candidate
        if paper_data is None and canonical.title_candidate:
            paper_data, title_rate_limited = _search_by_title(canonical.title_candidate)
            is_rate_limited = is_rate_limited or title_rate_limited
            if paper_data:
                match_type = "matched_by_title"

        # Ap dung ket qua
        if paper_data and match_type:
            _apply_ss_data(canonical, paper_data, match_type)

            ss_title = paper_data.get("title")
            _sync_title_to_papers(db, canonical, ss_title)

            logger.info(f"[SS enrich] Enriched: {cid} via {match_type}")
        elif is_rate_limited:
            canonical.enrichment_status = "rate_limited"
            canonical.match_status = "rate_limited"
            canonical.metadata_source = "semantic_scholar"
            logger.info("[SS enrich] Rate limited after %s attempts. Please retry after 5 minutes: %s", SS_MAX_ATTEMPTS, cid)
        else:
            canonical.enrichment_status = "unmatched"
            canonical.match_status = "unmatched"
            logger.info(f"[SS enrich] Unmatched: {cid}")

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception(f"[SS enrich] Error processing canonical_id={canonical_document_id}")
        raise
    finally:
        db.close()