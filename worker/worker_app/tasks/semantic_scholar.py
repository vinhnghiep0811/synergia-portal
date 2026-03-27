import logging
import sys
import time
from uuid import UUID

import httpx

sys.path.append("/backend")

from app.core.database import SessionLocal
from app.models.canonical_document import CanonicalDocument

logger = logging.getLogger(__name__)

SS_API_BASE = "https://api.semanticscholar.org/graph/v1"

# Cac truong can lay tu Semantic Scholar
SS_FIELDS = "title,authors,year,venue,abstract,externalIds"

# Nguong similarity de chap nhan match khi tim qua title (0.0 - 1.0)
TITLE_MATCH_THRESHOLD = 0.82


# -------------------------------------------------------
# Helper: tinh similarity don gian giua 2 chuoi khong can thu vien
# -------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Chuyen ve lowercase, bo dau cau de so sanh."""
    import re
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def _title_similarity(a: str, b: str) -> float:
    """
    Tinh he so Jaccard similarity giua 2 chuoi dua tren tap tu.
    Khong can thu vien ngoai, du dung cho viec so sanh title paper.
    """
    if not a or not b:
        return 0.0
    set_a = set(_normalize_title(a).split())
    set_b = set(_normalize_title(b).split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


# -------------------------------------------------------
# Helper: goi Semantic Scholar, co retry don gian
# -------------------------------------------------------

def _get_by_doi(doi: str) -> dict | None:
    """
    Goi truc tiep theo DOI.
    Tra ve dict du lieu paper hoac None neu khong tim thay.
    """
    url = f"{SS_API_BASE}/paper/{doi}"
    params = {"fields": SS_FIELDS}

    for attempt in range(3):
        try:
            resp = httpx.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                logger.info(f"[SS] DOI not found: {doi}")
                return None
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"[SS] Rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            logger.warning(f"[SS] Unexpected status {resp.status_code} for DOI {doi}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"[SS] Request error attempt {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(2)

    return None


def _search_by_title(title: str) -> dict | None:
    """
    Tim kiem theo title, lay ket qua dau tien co similarity >= nguong.
    Tra ve dict du lieu paper hoac None neu khong du tin cay.
    """
    url = f"{SS_API_BASE}/paper/search"
    params = {
        "query": title,
        "limit": 5,
        "fields": SS_FIELDS,
    }

    for attempt in range(3):
        try:
            resp = httpx.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", [])
                if not results:
                    return None

                # So sanh similarity voi tung ket qua, lay cai tot nhat
                best_paper = None
                best_score = 0.0
                for paper in results:
                    ss_title = paper.get("title", "")
                    score = _title_similarity(title, ss_title)
                    if score > best_score:
                        best_score = score
                        best_paper = paper

                if best_score >= TITLE_MATCH_THRESHOLD:
                    logger.info(
                        f"[SS] Title match: score={best_score:.2f} "
                        f"query='{title[:60]}' matched='{best_paper.get('title', '')[:60]}'"
                    )
                    # Gan score vao de luu vao DB
                    best_paper["_match_score"] = best_score
                    return best_paper
                else:
                    logger.info(
                        f"[SS] No confident match: best_score={best_score:.2f} for '{title[:60]}'"
                    )
                    return None

            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"[SS] Rate limited, waiting {wait}s")
                time.sleep(wait)
                continue

            logger.warning(f"[SS] Search status {resp.status_code} for title '{title[:60]}'")
            return None

        except httpx.RequestError as e:
            logger.warning(f"[SS] Request error attempt {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(2)

    return None


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

        # Neu da duoc enrich roi thi bo qua (canonical caching)
        if canonical.enrichment_status == "enriched":
            logger.info(f"[SS enrich] Already enriched, skipping: {cid}")
            return

        logger.info(f"[SS enrich] Start enriching canonical_id={cid}, doi={canonical.doi}")

        paper_data = None
        match_type = None

        # Uu tien DOI
        if canonical.doi:
            paper_data = _get_by_doi(canonical.doi)
            if paper_data:
                match_type = "matched_by_doi"

        # Fallback: tim theo title_candidate
        if paper_data is None and canonical.title_candidate:
            paper_data = _search_by_title(canonical.title_candidate)
            if paper_data:
                match_type = "matched_by_title"

        # Ap dung ket qua
        if paper_data and match_type:
            _apply_ss_data(canonical, paper_data, match_type)
            logger.info(f"[SS enrich] Enriched: {cid} via {match_type}")
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