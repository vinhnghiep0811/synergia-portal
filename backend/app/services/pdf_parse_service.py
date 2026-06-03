import hashlib
import logging
import re
from typing import Optional, Tuple, TypedDict, List

import pdfplumber

logger = logging.getLogger(__name__)

DOI_REGEX = re.compile(r"(?<![\d.])10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
REFERENCE_HEADING_REGEX = re.compile(
    r"(?im)^\s*(references|bibliography|works\s+cited|literature\s+cited)\s*$"
)
DOI_CONTEXT_MARKERS = ("doi", "doi.org/", "dx.doi.org/")
DOI_SCAN_CHARS = 12000
DOI_CONTEXT_CHARS = 90
MONTH_NAME_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)\.?"
)
PUBLICATION_MONTH_DAY_HEADER_REGEX = re.compile(
    rf"^(?:[A-Z][A-Za-z.&'+-]*(?:\s+[A-Z][A-Za-z.&'+-]*){{0,5}}\s+)?"
    rf"{MONTH_NAME_PATTERN}\s+\d{{1,2}},?\s*\(?\d{{4}}\)?$",
    re.IGNORECASE,
)
PUBLICATION_DAY_MONTH_HEADER_REGEX = re.compile(
    rf"^(?:[A-Z][A-Za-z.&'+-]*(?:\s+[A-Z][A-Za-z.&'+-]*){{0,5}}\s+)?"
    rf"\d{{1,2}}\s+{MONTH_NAME_PATTERN},?\s*\(?\d{{4}}\)?$",
    re.IGNORECASE,
)
ARTICLE_TYPE_LABELS = {
    "article",
    "brief report",
    "case report",
    "communication",
    "editorial",
    "letter",
    "opinion",
    "perspective",
    "research",
    "research article",
    "review",
    "review article",
    "short communication",
}

class PageText(TypedDict):
    page: int
    text: str

def strip_nul_chars(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.replace("\x00", "")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_ligatures(text: str) -> str:
    ligatures = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
    }
    for k, v in ligatures.items():
        text = text.replace(k, v)
    return text


def extract_pdf_full_text(
    file_path: str,
    max_pages: Optional[int] = None,
) -> str:
    texts: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]

        for page in pages:
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            page_text = strip_nul_chars(page_text)
            page_text = normalize_ligatures(page_text)

            if page_text.strip():
                texts.append(page_text.strip())

    full_text = "\n\n".join(texts).strip()

    if not full_text:
        raise ValueError("Could not extract full text from PDF")

    return full_text


def is_likely_noise(word: dict, page_width: float, page_height: float) -> bool:
    text = strip_nul_chars(word.get("text", ""))
    if not text:
        return True

    if not word.get("upright", True):
        return True

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)
    top = word.get("top", 0)
    bottom = word.get("bottom", 0)
    height = bottom - top
    width = x1 - x0

    if top < 10 or bottom > page_height - 10:
        return True

    if height > width * 1.5 and len(text) <= 3:
        return True

    return False


def group_words_into_lines(words: list[dict], y_tolerance: float = 4.0) -> list[list[dict]]:
    """
    Gom word thành từng dòng dựa trên tâm dọc của bbox, robust hơn chỉ dùng top.
    """
    if not words:
        return []

    def y_center(w: dict) -> float:
        return (w["top"] + w["bottom"]) / 2

    words = sorted(words, key=lambda w: (y_center(w), w["x0"]))

    lines: list[list[dict]] = []
    current_line = [words[0]]
    current_center = y_center(words[0])

    for w in words[1:]:
        wc = y_center(w)
        if abs(wc - current_center) <= y_tolerance:
            current_line.append(w)
            current_center = sum(y_center(x) for x in current_line) / len(current_line)
        else:
            lines.append(sorted(current_line, key=lambda x: x["x0"]))
            current_line = [w]
            current_center = wc

    lines.append(sorted(current_line, key=lambda x: x["x0"]))
    return lines


def line_text(line: list[dict]) -> str:
    if not line:
        return ""

    pieces = []
    prev = None

    for w in sorted(line, key=lambda x: x["x0"]):
        text = strip_nul_chars(w.get("text", ""))
        if not text:
            continue

        if prev is not None:
            gap = w["x0"] - prev["x1"]
            if gap > 1.5:
                pieces.append(" ")

        pieces.append(text)
        prev = w

    text = "".join(pieces)
    text = normalize_ligatures(text)
    text = normalize_space(text)

    text = re.sub(r"\s+([:;,.\)])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)

    return text


def line_avg_size(line: list[dict]) -> float:
    sizes = [w["size"] for w in line if "size" in w]
    return sum(sizes) / len(sizes) if sizes else 0.0


def _extract_lines_from_words(page) -> list[dict]:
    words = page.extract_words(extra_attrs=["size", "fontname", "upright"])
    if not words:
        return []

    filtered = [
        w for w in words
        if not is_likely_noise(w, page.width, page.height)
        and w["top"] < page.height * 0.45
    ]

    grouped = group_words_into_lines(filtered, y_tolerance=3.0)

    lines = []
    for line in grouped:
        text = normalize_ligatures(line_text(line))
        if not text:
            continue

        lines.append({
            "text": text,
            "top": min(w["top"] for w in line),
            "x0": min(w["x0"] for w in line),
            "x1": max(w["x1"] for w in line),
            "width": max(w["x1"] for w in line) - min(w["x0"] for w in line),
            "avg_size": line_avg_size(line),
        })
    return lines


def _extract_lines_from_chars(page) -> list[dict]:
    chars = page.chars
    if not chars:
        return []

    filtered = []
    for ch in chars:
        text = strip_nul_chars(ch.get("text", ""))
        if not text:
            continue
        if not ch.get("upright", True):
            continue
        if ch["top"] >= page.height * 0.45:
            continue
        if ch["x0"] < 20 or ch["x1"] > page.width - 20:
            continue
        filtered.append(ch)

    if not filtered:
        return []

    filtered = sorted(filtered, key=lambda c: (c["top"], c["x0"]))

    char_lines = []
    current = [filtered[0]]
    current_top = filtered[0]["top"]

    for ch in filtered[1:]:
        if abs(ch["top"] - current_top) <= 3.0:
            current.append(ch)
        else:
            char_lines.append(sorted(current, key=lambda x: x["x0"]))
            current = [ch]
            current_top = ch["top"]
    char_lines.append(sorted(current, key=lambda x: x["x0"]))

    lines = []
    for line in char_lines:
        pieces = []
        prev = None
        avg_size = sum(ch.get("size", 0) for ch in line) / len(line)

        for ch in line:
            t = ch.get("text", "")
            if prev is not None:
                gap = ch["x0"] - prev["x1"]
                if gap > max(1.2, avg_size * 0.18):
                    pieces.append(" ")
            pieces.append(t)
            prev = ch

        text = normalize_space(normalize_ligatures("".join(pieces)))
        if not text:
            continue

        lines.append({
            "text": text,
            "top": min(ch["top"] for ch in line),
            "x0": min(ch["x0"] for ch in line),
            "x1": max(ch["x1"] for ch in line),
            "width": max(ch["x1"] for ch in line) - min(ch["x0"] for ch in line),
            "avg_size": avg_size,
        })

    return lines


def _looks_broken(lines: list[dict]) -> bool:
    if not lines:
        return True

    joined = " | ".join(line["text"] for line in lines[:8]).lower()

    broken_tokens = {"fi", "fl", "ff", "ffi", "ffl"}
    short_line_count = sum(1 for line in lines[:10] if line["text"].strip().lower() in broken_tokens)

    if short_line_count >= 1:
        return True

    if re.search(r"\b[a-z]{2}\s+nition\b", joined):
        return True

    dense_bad = 0
    for line in lines[:8]:
        text = line["text"]
        if len(text) >= 20 and " " not in text:
            dense_bad += 1
    if dense_bad >= 2:
        return True

    return False


def _is_non_title_text(text: str) -> bool:
    t = text.lower().strip()
    return (
        "doi:" in t
        or re.match(r"^abstract\b", t) is not None
        or re.match(r"^keywords?\b", t) is not None
        or "downloaded from" in t
        or "creative commons" in t
        or "open access" in t
        or "published by" in t
        or "@" in t
        or _looks_like_article_type_label(text)
        or _looks_like_publication_header(text)
        or _looks_like_author_line(text)
    )


def _looks_like_article_type_label(text: str) -> bool:
    normalized = normalize_space(text).strip(" .:").lower()
    return normalized in ARTICLE_TYPE_LABELS


def _looks_like_publication_header(text: str) -> bool:
    normalized = normalize_space(text).strip(" .")
    if not normalized or len(normalized) > 90:
        return False

    return (
        PUBLICATION_MONTH_DAY_HEADER_REGEX.match(normalized) is not None
        or PUBLICATION_DAY_MONTH_HEADER_REGEX.match(normalized) is not None
    )


def _looks_like_author_line(text: str) -> bool:
    normalized = normalize_space(text)
    if not normalized:
        return False

    normalized = _strip_author_affiliation_markers(normalized)
    has_author_separator = "," in normalized or ";" in normalized or re.search(r"\band\b", normalized)

    if has_author_separator:
        chunks = [
            chunk.strip(" .;:()[]{}")
            for chunk in re.split(r"\s*(?:,|;|\band\b)\s*", normalized)
            if chunk.strip()
        ]
        if len(chunks) < 2:
            return False

        return all(_is_author_name_chunk(chunk) for chunk in chunks)

    return _looks_like_initialed_author_sequence(normalized)


def _strip_author_affiliation_markers(text: str) -> str:
    text = re.sub(r"([,;])\s*[\d*†‡§]+\s*", r"\1 ", text)
    text = re.sub(r"^\s*[\d*†‡§]+\s*", "", text)
    text = re.sub(r"(?<=[A-Za-z])\s*[\d*†‡§]+(?=(?:\s|,|;|$))", "", text)
    text = re.sub(r"[\u00b9\u00b2\u00b3\u2070-\u2079]+", "", text)
    return normalize_space(text)


def _is_author_name_chunk(chunk: str) -> bool:
    chunk = _strip_author_affiliation_markers(chunk).strip(" .;:()[]{}")
    if not chunk:
        return False

    if re.fullmatch(r"[A-Z][a-z]+[A-Z]\.[A-Z][A-Za-z-]+", chunk):
        return True

    words = [word for word in chunk.split(" ") if word]
    if not 2 <= len(words) <= 5:
        return False

    meaningful_words = 0
    for word in words:
        cleaned = word.strip(" ;:()[]{}")
        if not cleaned:
            continue

        if re.fullmatch(r"(?:[A-Z]\.){1,4}", cleaned):
            meaningful_words += 1
            continue

        if re.fullmatch(r"[A-Z][A-Za-z]+(?:[-'][A-Z]?[A-Za-z]+)*", cleaned):
            meaningful_words += 1
            continue

        if cleaned.lower() in {"de", "del", "da", "di", "la", "le", "van", "von"}:
            continue

        return False

    return meaningful_words >= 2


def _looks_like_initialed_author_sequence(text: str) -> bool:
    matches = re.findall(
        r"(?:[A-Z]\.){1,4}\s*[A-Z][A-Za-z]+(?:[-'][A-Z]?[A-Za-z]+)*",
        text,
    )
    if len(matches) < 2:
        return False

    compact_text = re.sub(r"\s+", "", text)
    compact_matches = sum(len(re.sub(r"\s+", "", match)) for match in matches)

    return compact_matches / max(1, len(compact_text)) >= 0.75


def _alpha_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text)


def _is_probable_title_line(line: dict, page_width: float) -> bool:
    text = normalize_space(line["text"])
    words = _alpha_words(text)
    if len(words) < 4:
        return False
    if _is_non_title_text(text):
        return False
    if line["avg_size"] < 10.5:
        return False
    if line["width"] < page_width * 0.30:
        return False

    return any(char.isupper() for char in text)


def _looks_like_contextual_masthead(
    line: dict,
    lines: list[dict],
    page_width: float,
) -> bool:
    text = normalize_space(line["text"])
    words = _alpha_words(text)
    if not text or len(text) > 48 or len(words) > 4:
        return False
    if line["top"] > 95:
        return False
    if line["width"] > page_width * 0.45:
        return False
    if ":" in text:
        return False

    return any(
        candidate["top"] > line["top"]
        and candidate["top"] - line["top"] <= 150
        and candidate["avg_size"] >= line["avg_size"] - 2.8
        and _is_probable_title_line(candidate, page_width)
        for candidate in lines
    )


def _is_contextual_non_title_line(
    line: dict,
    lines: list[dict],
    page_width: float,
) -> bool:
    return (
        _is_non_title_text(line["text"])
        or _looks_like_contextual_masthead(line, lines, page_width)
    )


def _select_title_from_lines(lines: list[dict], page_width: float) -> Optional[str]:
    if not lines:
        return None

    usable = [
        line
        for line in lines
        if not _is_contextual_non_title_line(line, lines, page_width)
    ]
    if not usable:
        return None

    page_center = page_width / 2

    scored = []
    for line in usable:
        center_x = (line["x0"] + line["x1"]) / 2
        text = line["text"]

        alpha_count = sum(1 for c in text if c.isalpha())
        upper_ratio = (
            sum(1 for c in text if c.isupper()) / alpha_count
            if alpha_count else 0
        )

        score = (
            line["avg_size"] * 4
            - line["top"] * 0.03
            - abs(center_x - page_center) * 0.01
        )

        if upper_ratio > 0.85 and len(text) > 25 and "," not in text and ":" not in text:
            score -= 4

        scored.append((score, line))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    seed = scored[0][1]

    sorted_lines = sorted(usable, key=lambda x: x["top"])
    seed_idx = sorted_lines.index(seed)

    selected = [seed]

    prev = seed
    for i in range(seed_idx - 1, -1, -1):
        line = sorted_lines[i]
        gap = prev["top"] - line["top"]
        if gap > 28:
            break
        if line["avg_size"] < seed["avg_size"] - 2.2:
            break
        if _is_non_title_text(line["text"]):
            break

        selected.insert(0, line)
        prev = line

    prev = seed
    for i in range(seed_idx + 1, len(sorted_lines)):
        line = sorted_lines[i]
        gap = line["top"] - prev["top"]
        if gap > 28:
            break
        if line["avg_size"] < seed["avg_size"] - 2.2:
            break
        if _is_non_title_text(line["text"]):
            break

        selected.append(line)
        prev = line

    title = normalize_space(" ".join(line["text"] for line in selected))
    return title or None


def build_text_preview(full_text: str, preview_chars: int = 2000) -> str:
    full_text = strip_nul_chars(full_text).strip()
    return full_text[:preview_chars] if full_text else ""


def extract_pdf_text_and_preview(
    file_path: str,
    max_pages: int = 3,
    preview_chars: int = 2000,
) -> Tuple[str, str]:
    """
    Dùng cho parse/canonical flow hiện tại:
    - chỉ lấy một phần số trang đầu để giữ behavior cũ ổn định
    - full_text ở đây là full_text giới hạn theo max_pages
    """
    full_text = extract_pdf_full_text(
        file_path=file_path,
        max_pages=max_pages,
    )
    preview = build_text_preview(full_text, preview_chars=preview_chars)
    return full_text, preview

def _clean_extracted_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', text)
    text = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', text)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = re.sub(r'(?<=[,.;:])(?=[A-Za-z])', ' ', text)
    return text.strip()


def _is_likely_two_column_page(page) -> bool:
    try:
        words = page.extract_words(x_tolerance=2, y_tolerance=3) or []
    except Exception:
        return False

    if len(words) < 180:
        return False

    mid = page.width / 2
    gutter = max(28, page.width * 0.055)

    left = 0
    right = 0
    middle = 0
    for word in words:
        center = (word.get("x0", 0) + word.get("x1", 0)) / 2
        if center < mid - gutter:
            left += 1
        elif center > mid + gutter:
            right += 1
        else:
            middle += 1

    if left < 80 or right < 80:
        return False

    return (middle / max(1, left + right)) < 0.16


def _extract_two_column_page_text(page) -> str:
    if not _is_likely_two_column_page(page):
        return ""

    mid = page.width / 2
    gutter = max(6, page.width * 0.015)
    bboxes = [
        (0, 0, mid - gutter, page.height),
        (mid + gutter, 0, page.width, page.height),
    ]

    parts: list[str] = []
    for bbox in bboxes:
        try:
            text = page.crop(bbox).extract_text(x_tolerance=2, y_tolerance=3) or ""
        except Exception:
            text = ""

        text = _clean_extracted_text(normalize_ligatures(strip_nul_chars(text)))
        if len(text.split()) >= 40:
            parts.append(text)

    if len(parts) != 2:
        return ""

    column_text = "\n\n".join(parts).strip()
    return column_text


def _extract_page_text_for_llm(page) -> str:
    default_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
    default_text = _clean_extracted_text(normalize_ligatures(strip_nul_chars(default_text)))

    column_text = _extract_two_column_page_text(page)
    if column_text and len(column_text) >= len(default_text) * 0.65:
        return column_text

    return default_text

def extract_pdf_text_for_llm(
    file_path: str,
    preview_chars: int = 2000,
) -> Tuple[str, str, List[PageText]]:
    """
    Dùng cho LLM pipeline:
    - cố gắng lấy full text của toàn bộ PDF
    - preview chỉ để hiển thị nhanh / debug
    """
    pages: List[PageText] = []
    full_parts: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = _extract_page_text_for_llm(page).strip()

            pages.append({
                "page": idx,
                "text": text,
            })

            if text:
                full_parts.append(f"[Page {idx}]\n{text}")

    full_text = "\n\n".join(full_parts)
    preview = build_text_preview(full_text, preview_chars=preview_chars)
    return full_text, preview, pages


def normalize_doi(raw_doi: str) -> str:
    doi = strip_nul_chars(raw_doi).strip().lower()
    doi = doi.rstrip(").,;:]}")
    return doi


def _text_before_references(text: str) -> str:
    match = REFERENCE_HEADING_REGEX.search(text)
    if not match:
        return text
    return text[: match.start()]


def _has_doi_context(text: str, start: int, end: int) -> bool:
    context_start = max(0, start - DOI_CONTEXT_CHARS)
    context_end = min(len(text), end + DOI_CONTEXT_CHARS)
    context = text[context_start:context_end].lower()
    return any(marker in context for marker in DOI_CONTEXT_MARKERS)


def detect_doi(text: str) -> Optional[str]:
    text = strip_nul_chars(text)
    candidate_text = _text_before_references(text)[:DOI_SCAN_CHARS]
    matches = list(DOI_REGEX.finditer(candidate_text))
    if not matches:
        return None

    for match in matches:
        if _has_doi_context(candidate_text, match.start(), match.end()):
            return normalize_doi(match.group(0))

    return normalize_doi(matches[0].group(0))


def clean_line(line: str) -> str:
    line = strip_nul_chars(line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def detect_title(file_path: str) -> Optional[str]:
    with pdfplumber.open(file_path) as pdf:
        if not pdf.pages:
            return None

        first_page = pdf.pages[0]

        word_lines = _extract_lines_from_words(first_page)
        if word_lines and not _looks_broken(word_lines):
            title = _select_title_from_lines(word_lines, first_page.width)
            if title:
                return title

        char_lines = _extract_lines_from_chars(first_page)
        if char_lines:
            title = _select_title_from_lines(char_lines, first_page.width)
            if title:
                return title

        title = _select_title_from_lines(word_lines, first_page.width)
        return title


def normalize_text_for_fingerprint(text: str) -> str:
    text = strip_nul_chars(text).lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def build_fingerprint(text: str, title: Optional[str] = None, max_chars: int = 4000) -> str:
    normalized_text = normalize_text_for_fingerprint(text[:max_chars])
    normalized_title = normalize_text_for_fingerprint(title or "")

    fingerprint_source = f"{normalized_title}\n{normalized_text}".strip()
    if not fingerprint_source:
        raise ValueError("Could not build fingerprint from empty content")

    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
