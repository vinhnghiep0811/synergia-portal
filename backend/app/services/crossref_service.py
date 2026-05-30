from __future__ import annotations

import html
import logging
import os
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import httpx


logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org/v1"
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
CROSSREF_USER_AGENT = os.getenv(
    "CROSSREF_USER_AGENT",
    "SynergiaPortal/0.1 (https://localhost)",
).strip()
CROSSREF_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("CROSSREF_TIMEOUT_SECONDS", "15")),
)
CROSSREF_MIN_INTERVAL_SECONDS = max(
    0.1,
    float(os.getenv("CROSSREF_MIN_INTERVAL_SECONDS", "0.25")),
)
CROSSREF_TITLE_MATCH_THRESHOLD = max(
    0.0,
    min(1.0, float(os.getenv("CROSSREF_TITLE_MATCH_THRESHOLD", "0.82"))),
)
CROSSREF_LOG_BODY_MAX_CHARS = 4000
VENUE_STOPWORDS = {
    "a",
    "an",
    "and",
    "annual",
    "conference",
    "for",
    "in",
    "international",
    "of",
    "on",
    "proceedings",
    "symposium",
    "the",
    "workshop",
}

_crossref_rate_lock = threading.Lock()
_last_crossref_request_ts = 0.0


class CrossrefService:
    def __init__(
        self,
        timeout_seconds: float = CROSSREF_TIMEOUT_SECONDS,
        title_match_threshold: float = CROSSREF_TITLE_MATCH_THRESHOLD,
    ) -> None:
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.title_match_threshold = max(0.0, min(1.0, float(title_match_threshold)))

    def verify_metadata(
        self,
        primary_metadata: dict[str, Any],
        lookup_doi: str | None = None,
        lookup_title: str | None = None,
    ) -> dict[str, Any]:
        doi = self._normalize_doi(
            lookup_doi
            or primary_metadata.get("doi")
            or (primary_metadata.get("external_ids") or {}).get("DOI")
        )
        title = lookup_title or primary_metadata.get("title")
        queried_by = "doi" if doi else "title" if title else "none"

        result: dict[str, Any] | None = None
        rate_limited = False
        error = None

        if doi:
            result, rate_limited, error = self._get_by_doi(doi)

        if result is None and title and not rate_limited:
            result, rate_limited, error = self._search_by_title(title)
            if result is not None:
                queried_by = "title"

        if rate_limited:
            return self._empty_verification(
                status="rate_limited",
                primary_metadata=primary_metadata,
                queried_by=queried_by,
                error=error,
            )

        if error:
            return self._empty_verification(
                status="error",
                primary_metadata=primary_metadata,
                queried_by=queried_by,
                error=error,
            )

        if result is None:
            return self._empty_verification(
                status="not_found",
                primary_metadata=primary_metadata,
                queried_by=queried_by,
            )

        crossref_metadata = self.normalize_work(result)
        field_results, confidence, conflicts = self._compare_metadata(
            primary_metadata,
            crossref_metadata,
        )

        if conflicts:
            status = "conflict"
        elif confidence >= 0.82:
            status = "verified"
        elif confidence >= 0.65:
            status = "partial"
        else:
            status = "weak"

        return {
            "provider": "crossref",
            "status": status,
            "queried_by": queried_by,
            "confidence": round(confidence, 4),
            "conflicts": conflicts,
            "fields": field_results,
            "primary_metadata": self._compact_metadata(primary_metadata),
            "crossref_metadata": crossref_metadata,
        }

    def normalize_work(self, item: dict[str, Any]) -> dict[str, Any]:
        title = self._first_text(item.get("title"))
        authors = [name for name in (self._format_author(a) for a in item.get("author", [])) if name]
        venue = (
            self._first_text(item.get("container-title"))
            or self._first_text(item.get("short-container-title"))
            or (item.get("event") or {}).get("name")
            or item.get("publisher")
        )

        return {
            "source": "crossref",
            "doi": self._normalize_doi(item.get("DOI")),
            "title": title,
            "authors": authors,
            "year": self._extract_year(item),
            "venue": venue,
            "abstract": self._clean_abstract(item.get("abstract")),
            "type": item.get("type"),
            "url": item.get("URL"),
        }

    def _get_by_doi(self, doi: str) -> tuple[dict[str, Any] | None, bool, str | None]:
        url = f"{CROSSREF_API_BASE}/works/{doi}"
        params = self._base_params()
        try:
            resp = self._request("GET", url, params)
        except httpx.RequestError as exc:
            logger.warning("[Crossref] DOI request failed doi=%s error=%s", doi, exc)
            return None, False, str(exc)

        if resp.status_code == 200:
            return resp.json().get("message"), False, None
        if resp.status_code == 404:
            logger.info("[Crossref] DOI not found: %s", doi)
            return None, False, None
        if resp.status_code == 429:
            logger.warning("[Crossref] Rate limited for DOI %s", doi)
            return None, True, "rate_limited"
        if resp.status_code in {401, 403}:
            logger.warning("[Crossref] Access denied status=%s doi=%s", resp.status_code, doi)
            return None, False, f"status_{resp.status_code}"
        if 500 <= resp.status_code < 600:
            logger.warning("[Crossref] Server error status=%s doi=%s", resp.status_code, doi)
            return None, False, f"status_{resp.status_code}"

        logger.warning("[Crossref] Unexpected DOI status=%s doi=%s", resp.status_code, doi)
        return None, False, f"status_{resp.status_code}"

    def _search_by_title(self, title: str) -> tuple[dict[str, Any] | None, bool, str | None]:
        url = f"{CROSSREF_API_BASE}/works"
        params = {
            **self._base_params(),
            "query.title": title,
            "rows": 5,
        }

        try:
            resp = self._request("GET", url, params)
        except httpx.RequestError as exc:
            logger.warning("[Crossref] Title request failed title=%s error=%s", title[:80], exc)
            return None, False, str(exc)

        if resp.status_code == 429:
            logger.warning("[Crossref] Rate limited for title query '%s'", title[:80])
            return None, True, "rate_limited"
        if resp.status_code != 200:
            logger.warning(
                "[Crossref] Title search status=%s title=%s",
                resp.status_code,
                title[:80],
            )
            return None, False, f"status_{resp.status_code}"

        items = (resp.json().get("message") or {}).get("items", [])
        best_item = None
        best_score = 0.0
        for item in items:
            candidate_title = self._first_text(item.get("title")) or ""
            score = self._text_similarity(title, candidate_title)
            if score > best_score:
                best_score = score
                best_item = item

        if best_item is None or best_score < self.title_match_threshold:
            logger.info(
                "[Crossref] No confident title match score=%.4f threshold=%.2f title=%s",
                best_score,
                self.title_match_threshold,
                title[:80],
            )
            return None, False, None

        logger.info(
            "[Crossref] Title match score=%.4f title=%s",
            best_score,
            title[:80],
        )
        return best_item, False, None

    def _request(self, method: str, url: str, params: dict[str, Any]) -> httpx.Response:
        self._wait_for_rate_slot()
        headers = self._headers()
        logger.info(
            "[Crossref HTTP REQUEST] method=%s url=%s params=%s",
            method,
            url,
            {k: v for k, v in params.items() if k != "mailto"},
        )
        resp = httpx.request(
            method,
            url,
            params=params,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        logger.info(
            "[Crossref HTTP RESPONSE] method=%s url=%s status=%s body=%s",
            method,
            str(resp.request.url),
            resp.status_code,
            self._truncate(resp.text),
        )
        return resp

    def _base_params(self) -> dict[str, Any]:
        return {"mailto": CROSSREF_MAILTO} if CROSSREF_MAILTO else {}

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": CROSSREF_USER_AGENT} if CROSSREF_USER_AGENT else {}

    def _wait_for_rate_slot(self) -> None:
        global _last_crossref_request_ts

        with _crossref_rate_lock:
            now = time.monotonic()
            elapsed = now - _last_crossref_request_ts
            if elapsed < CROSSREF_MIN_INTERVAL_SECONDS:
                time.sleep(CROSSREF_MIN_INTERVAL_SECONDS - elapsed)
            _last_crossref_request_ts = time.monotonic()

    def _empty_verification(
        self,
        status: str,
        primary_metadata: dict[str, Any],
        queried_by: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "provider": "crossref",
            "status": status,
            "queried_by": queried_by,
            "confidence": 0.0,
            "conflicts": [],
            "fields": {},
            "primary_metadata": self._compact_metadata(primary_metadata),
            "crossref_metadata": None,
        }
        if error:
            payload["error"] = error
        return payload

    def _compare_metadata(
        self,
        primary: dict[str, Any],
        crossref: dict[str, Any],
    ) -> tuple[dict[str, Any], float, list[str]]:
        fields: dict[str, Any] = {}
        weighted_scores: list[tuple[float, float]] = []
        conflicts: list[str] = []

        doi_score, doi_status = self._compare_doi(primary.get("doi"), crossref.get("doi"))
        fields["doi"] = {
            "status": doi_status,
            "score": doi_score,
            "primary": self._normalize_doi(primary.get("doi")),
            "crossref": crossref.get("doi"),
        }
        if doi_score is not None:
            weighted_scores.append((0.35, doi_score))
            if doi_status == "mismatch":
                conflicts.append("doi")

        title_score = self._compare_text_field(primary.get("title"), crossref.get("title"))
        fields["title"] = title_score
        if title_score["score"] is not None:
            weighted_scores.append((0.30, title_score["score"]))
            if title_score["status"] == "mismatch":
                conflicts.append("title")

        year_score = self._compare_year(primary.get("year"), crossref.get("year"))
        fields["year"] = year_score

        strong_identity_match = (
            fields["doi"]["status"] == "match"
            or (
                title_score["status"] == "match"
                and (
                    year_score["status"] in {"match", "partial", "missing"}
                )
            )
        )

        author_score = self._compare_authors(primary.get("authors"), crossref.get("authors"))
        fields["authors"] = author_score
        if author_score["score"] is not None:
            weighted_scores.append((0.15, author_score["score"]))
            if author_score["status"] == "mismatch" and not strong_identity_match:
                conflicts.append("authors")

        if year_score["score"] is not None:
            weighted_scores.append((0.10, year_score["score"]))
            if year_score["status"] == "mismatch":
                conflicts.append("year")

        venue_score = self._compare_venue(primary.get("venue"), crossref.get("venue"))
        fields["venue"] = venue_score
        if venue_score["score"] is not None:
            weighted_scores.append((0.10, venue_score["score"]))
            if venue_score["status"] == "mismatch" and not strong_identity_match:
                conflicts.append("venue")

        abstract_score = self._compare_text_field(
            primary.get("abstract"),
            crossref.get("abstract"),
            match_threshold=0.60,
            mismatch_threshold=0.30,
        )
        fields["abstract"] = abstract_score

        if not weighted_scores:
            return fields, 0.0, conflicts

        total_weight = sum(weight for weight, _score in weighted_scores)
        confidence = sum(weight * score for weight, score in weighted_scores) / total_weight
        return fields, confidence, conflicts

    def _compare_doi(self, primary_doi: Any, crossref_doi: Any) -> tuple[float | None, str]:
        primary = self._normalize_doi(primary_doi)
        crossref = self._normalize_doi(crossref_doi)
        if not primary or not crossref:
            return None, "missing"
        return (1.0, "match") if primary == crossref else (0.0, "mismatch")

    def _compare_text_field(
        self,
        primary_text: Any,
        crossref_text: Any,
        match_threshold: float = 0.82,
        mismatch_threshold: float = 0.55,
    ) -> dict[str, Any]:
        primary = str(primary_text).strip() if primary_text else None
        crossref = str(crossref_text).strip() if crossref_text else None
        if not primary or not crossref:
            return {
                "status": "missing",
                "score": None,
                "primary": primary,
                "crossref": crossref,
            }

        score = self._text_similarity(primary, crossref)
        if score >= match_threshold:
            status = "match"
        elif score <= mismatch_threshold:
            status = "mismatch"
        else:
            status = "partial"

        return {
            "status": status,
            "score": round(score, 4),
            "primary": primary,
            "crossref": crossref,
        }

    def _compare_authors(self, primary_authors: Any, crossref_authors: Any) -> dict[str, Any]:
        primary = self._parse_author_list(primary_authors)
        crossref = self._parse_author_list(crossref_authors)
        if not primary or not crossref:
            return {
                "status": "missing",
                "score": None,
                "primary": primary_authors or [],
                "crossref": crossref_authors or [],
            }

        pair_scores: list[tuple[float, int, int]] = []
        for primary_idx, primary_author in enumerate(primary):
            for crossref_idx, crossref_author in enumerate(crossref):
                pair_scores.append(
                    (
                        self._author_similarity(primary_author, crossref_author),
                        primary_idx,
                        crossref_idx,
                    )
                )

        matched_primary: set[int] = set()
        matched_crossref: set[int] = set()
        matched_pairs: list[dict[str, Any]] = []
        total_score = 0.0

        for pair_score, primary_idx, crossref_idx in sorted(pair_scores, reverse=True):
            if primary_idx in matched_primary or crossref_idx in matched_crossref:
                continue
            matched_primary.add(primary_idx)
            matched_crossref.add(crossref_idx)
            total_score += pair_score
            matched_pairs.append(
                {
                    "primary": primary[primary_idx]["original"],
                    "crossref": crossref[crossref_idx]["original"],
                    "score": round(pair_score, 4),
                }
            )

        denominator = max(len(primary), len(crossref))
        score = total_score / denominator if denominator else 0.0
        first_author_score = self._author_similarity(primary[0], crossref[0])
        first_author_matches = first_author_score >= 0.80

        if score >= 0.75 or (first_author_matches and score >= 0.55):
            status = "match"
        elif score >= 0.45 or first_author_matches:
            status = "partial"
        else:
            status = "mismatch"

        return {
            "status": status,
            "score": round(score, 4),
            "first_author_score": round(first_author_score, 4),
            "first_author_matches": first_author_matches,
            "primary": primary_authors or [],
            "crossref": crossref_authors or [],
            "matched_pairs": matched_pairs,
        }

    def _compare_venue(self, primary_venue: Any, crossref_venue: Any) -> dict[str, Any]:
        primary = str(primary_venue).strip() if primary_venue else None
        crossref = str(crossref_venue).strip() if crossref_venue else None
        if not primary or not crossref:
            return {
                "status": "missing",
                "score": None,
                "primary": primary,
                "crossref": crossref,
            }

        primary_tokens = self._venue_tokens(primary)
        crossref_tokens = self._venue_tokens(crossref)
        shared_tokens = primary_tokens & crossref_tokens
        token_jaccard = (
            len(shared_tokens) / len(primary_tokens | crossref_tokens)
            if primary_tokens and crossref_tokens
            else 0.0
        )
        primary_containment = (
            len(shared_tokens) / len(primary_tokens) if primary_tokens else 0.0
        )
        crossref_containment = (
            len(shared_tokens) / len(crossref_tokens) if crossref_tokens else 0.0
        )
        containment = max(primary_containment, crossref_containment)

        primary_acronyms = self._extract_acronyms(primary)
        crossref_acronyms = self._extract_acronyms(crossref)
        acronym_overlap = bool(primary_acronyms & crossref_acronyms)
        raw_score = self._text_similarity(primary, crossref)

        score = max(raw_score, token_jaccard)
        if containment >= 0.80:
            score = max(score, 0.88)
        elif containment >= 0.60:
            score = max(score, 0.72)
        elif containment >= 0.45:
            score = max(score, 0.55)

        if acronym_overlap:
            score = max(score, 0.72 if containment >= 0.45 else 0.55)

        if score >= 0.75:
            status = "match"
        elif score >= 0.45:
            status = "partial"
        else:
            status = "mismatch"

        return {
            "status": status,
            "score": round(score, 4),
            "primary": primary,
            "crossref": crossref,
            "shared_tokens": sorted(shared_tokens),
            "primary_containment": round(primary_containment, 4),
            "crossref_containment": round(crossref_containment, 4),
            "acronym_overlap": sorted(primary_acronyms & crossref_acronyms),
        }

    def _compare_year(self, primary_year: Any, crossref_year: Any) -> dict[str, Any]:
        primary = self._safe_int(primary_year)
        crossref = self._safe_int(crossref_year)
        if primary is None or crossref is None:
            return {
                "status": "missing",
                "score": None,
                "primary": primary,
                "crossref": crossref,
            }

        diff = abs(primary - crossref)
        if diff == 0:
            score = 1.0
            status = "match"
        elif diff == 1:
            score = 0.5
            status = "partial"
        else:
            score = 0.0
            status = "mismatch"

        return {
            "status": status,
            "score": score,
            "primary": primary,
            "crossref": crossref,
        }

    def _compact_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": metadata.get("source"),
            "doi": self._normalize_doi(metadata.get("doi")),
            "title": metadata.get("title"),
            "authors": metadata.get("authors") or [],
            "year": metadata.get("year"),
            "venue": metadata.get("venue"),
            "abstract": metadata.get("abstract"),
        }

    def _normalize_doi(self, doi: Any) -> str | None:
        if not doi:
            return None
        normalized = str(doi).strip().lower()
        normalized = re.sub(r"^https?://(dx\.)?doi\.org/", "", normalized)
        normalized = re.sub(r"^doi:\s*", "", normalized)
        normalized = normalized.strip().strip(".")
        return normalized or None

    def _normalize_author_list(self, authors: Any) -> list[str]:
        if not authors:
            return []
        normalized = []
        for author in authors:
            name = author.get("name") if isinstance(author, dict) else str(author)
            value = self._normalize_text(name)
            if value:
                normalized.append(value)
        return normalized

    def _parse_author_list(self, authors: Any) -> list[dict[str, Any]]:
        if not authors:
            return []

        parsed = []
        for author in authors:
            name = author.get("name") if isinstance(author, dict) else str(author)
            parts = self._parse_author_name(name)
            if parts["normalized"]:
                parsed.append(parts)
        return parsed

    def _parse_author_name(self, name: Any) -> dict[str, Any]:
        original = str(name or "").strip()
        if not original:
            return {
                "original": original,
                "normalized": "",
                "family": "",
                "given": [],
                "given_initials": [],
            }

        if "," in original:
            family_part, given_part = original.split(",", 1)
            family_tokens = self._normalize_text(family_part).split()
            given_tokens = self._normalize_text(given_part).split()
        else:
            tokens = self._normalize_text(original).split()
            family_tokens = tokens[-1:] if tokens else []
            given_tokens = tokens[:-1] if len(tokens) > 1 else []

        family = family_tokens[-1] if family_tokens else ""
        normalized = " ".join([*given_tokens, family]).strip()
        return {
            "original": original,
            "normalized": normalized,
            "family": family,
            "given": given_tokens,
            "given_initials": [token[0] for token in given_tokens if token],
        }

    def _author_similarity(self, primary: dict[str, Any], crossref: dict[str, Any]) -> float:
        if not primary["normalized"] or not crossref["normalized"]:
            return 0.0
        if primary["normalized"] == crossref["normalized"]:
            return 1.0

        family_score = self._name_token_similarity(primary["family"], crossref["family"])
        if family_score < 0.84:
            return 0.25 * family_score

        given_score = self._given_name_similarity(primary["given"], crossref["given"])
        return min(1.0, 0.65 * family_score + 0.35 * given_score)

    def _name_token_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        return SequenceMatcher(None, a, b).ratio()

    def _given_name_similarity(self, primary_given: list[str], crossref_given: list[str]) -> float:
        if not primary_given or not crossref_given:
            return 0.75

        primary_text = " ".join(primary_given)
        crossref_text = " ".join(crossref_given)
        if primary_text == crossref_text:
            return 1.0

        primary_initials = [token[0] for token in primary_given if token]
        crossref_initials = [token[0] for token in crossref_given if token]
        if primary_initials and crossref_initials:
            prefix_len = min(len(primary_initials), len(crossref_initials))
            if primary_initials[:prefix_len] == crossref_initials[:prefix_len]:
                shorter_has_initial = any(len(token) == 1 for token in primary_given + crossref_given)
                return 0.95 if shorter_has_initial else 0.85

        return self._text_similarity(primary_text, crossref_text)

    def _venue_tokens(self, venue: Any) -> set[str]:
        normalized = self._normalize_text(venue)
        return {
            token
            for token in normalized.split()
            if token
            and token not in VENUE_STOPWORDS
            and not token.isdigit()
            and len(token) > 1
        }

    def _extract_acronyms(self, text: Any) -> set[str]:
        if not text:
            return set()
        return {
            token.lower()
            for token in re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", str(text))
        }

    def _normalize_text(self, text: Any) -> str:
        if not text:
            return ""
        value = self._strip_accents(str(text))
        value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value

    def _strip_accents(self, text: str) -> str:
        return "".join(
            char
            for char in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(char)
        )

    def _text_similarity(self, a: str, b: str) -> float:
        na = self._normalize_text(a)
        nb = self._normalize_text(b)
        if not na or not nb:
            return 0.0
        if na.replace(" ", "") == nb.replace(" ", ""):
            return 1.0

        set_a = set(na.split())
        set_b = set(nb.split())
        token_score = len(set_a & set_b) / len(set_a | set_b) if (set_a and set_b) else 0.0
        seq_score = SequenceMatcher(None, na, nb).ratio()
        return 0.6 * seq_score + 0.4 * token_score

    def _first_text(self, value: Any) -> str | None:
        if isinstance(value, list):
            for item in value:
                if item:
                    return str(item).strip()
            return None
        if value:
            return str(value).strip()
        return None

    def _format_author(self, author: dict[str, Any]) -> str | None:
        name = author.get("name")
        if name:
            return str(name).strip()

        parts = [
            str(author.get("given") or "").strip(),
            str(author.get("family") or "").strip(),
        ]
        joined = " ".join(part for part in parts if part)
        return joined or None

    def _extract_year(self, item: dict[str, Any]) -> int | None:
        for key in ("published-print", "published-online", "published", "issued", "created"):
            value = item.get(key)
            date_parts = (value or {}).get("date-parts") if isinstance(value, dict) else None
            if date_parts and date_parts[0]:
                return self._safe_int(date_parts[0][0])
        return None

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clean_abstract(self, abstract: Any) -> str | None:
        if not abstract:
            return None
        value = html.unescape(str(abstract))
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def _truncate(self, text: str, max_chars: int = CROSSREF_LOG_BODY_MAX_CHARS) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}...<truncated>"
