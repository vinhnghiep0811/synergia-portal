import hashlib
import re
from typing import Optional, Tuple

import pdfplumber
import logging

logger = logging.getLogger(__name__)

DOI_REGEX = re.compile(r"(?<![\d.])10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


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

def is_likely_noise(word: dict, page_width: float, page_height: float) -> bool:
    text = strip_nul_chars(word.get("text", ""))
    if not text:
        return True

    # Bỏ chữ xoay dọc / không nằm ngang
    if not word.get("upright", True):
        return True

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)
    top = word.get("top", 0)
    bottom = word.get("bottom", 0)
    height = bottom - top
    width = x1 - x0

    # Bỏ text quá sát mép trên/dưới (header/footer)
    if top < 10 or bottom > page_height - 10:
        return True

    # Bỏ text quá sát mép trái/phải, thường là text dọc, số trang, note
    # if x0 < 20 or x1 > page_width - 20:
    #     return True

    # Bỏ word cực ngắn 1 ký tự nằm riêng lẻ, rất dễ là nhiễu
    # if len(text) == 1 and not text.isdigit():
    #     return True

    # Bỏ các khối quá cao và hẹp, dễ là chữ xoay hoặc artifact
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

            # nếu token rất sát nhau thì không chèn space
            if gap > 1.5:
                pieces.append(" ")

        pieces.append(text)
        prev = w

    text = "".join(pieces)
    text = normalize_ligatures(text)
    text = normalize_space(text)

    # cleanup punctuation
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

    # group chars into lines
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
                # heuristic chèn space
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

    if re.search(r"\b[a-z]{1,3}\s+[a-z]{4,}\b", joined) and "abstract" not in joined:
        # heuristic hơi rộng, chỉ dùng làm tín hiệu phụ
        pass

    # quá nhiều line toàn chữ dính liền
    dense_bad = 0
    for line in lines[:8]:
        text = line["text"]
        if len(text) >= 20 and " " not in text:
            dense_bad += 1
    if dense_bad >= 2:
        return True

    return False


def _is_non_title_text(text: str) -> bool:
    t = text.lower()
    return (
        "doi:" in t
        or "abstract" in t
        or "keywords" in t
        or "downloaded from" in t
        or "creative commons" in t
        or "open access" in t
        or "published by" in t
        or "@" in t
    )


def _select_title_from_lines(lines: list[dict], page_width: float) -> Optional[str]:
    if not lines:
        return None

    usable = [line for line in lines if not _is_non_title_text(line["text"])]
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

        # chỉ phạt author-like line khi thực sự giống author
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

    # mở rộng lên trên
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

    # mở rộng xuống dưới
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

def extract_pdf_text_and_preview(
    file_path: str,
    max_pages: int = 3,
    preview_chars: int = 2000,
) -> Tuple[str, str]:
    texts: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        pages = pdf.pages[:max_pages]
        for page in pages:
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            page_text = strip_nul_chars(page_text)
            if page_text.strip():
                texts.append(page_text)

    full_text = strip_nul_chars("\n".join(texts)).strip()
    preview = full_text[:preview_chars] if full_text else ""

    if not full_text:
        raise ValueError("Could not extract text from PDF")

    return full_text, preview


def normalize_doi(raw_doi: str) -> str:
    doi = strip_nul_chars(raw_doi).strip().lower()
    doi = doi.rstrip(").,;:]}")
    return doi


def detect_doi(text: str) -> Optional[str]:
    text = strip_nul_chars(text)
    match = DOI_REGEX.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0))


def clean_line(line: str) -> str:
    line = strip_nul_chars(line)
    line = re.sub(r"\s+", " ", line).strip()
    return line

def detect_title(file_path: str) -> Optional[str]:
    with pdfplumber.open(file_path) as pdf:
        if not pdf.pages:
            return None

        first_page = pdf.pages[0]
        for w in first_page.extract_words(extra_attrs=["size", "fontname", "upright"]):
            if w["top"] < first_page.height * 0.2:
                        logger.warning(
                            "[TITLE DEBUG WORD] text=%r x0=%.2f x1=%.2f top=%.2f",
                            w.get("text", ""),
                            w.get("x0", 0.0),
                            w.get("x1", 0.0),
                            w.get("top", 0.0),
                        )
                    
        word_lines = _extract_lines_from_words(first_page)
        logger.warning("[TITLE DEBUG] word_lines=%s", word_lines[:10])
        # if word_lines and not _looks_broken(word_lines):
        #     title = _select_title_from_lines(word_lines, first_page.width)
        #     if title:
        #         return title

        # char_lines = _extract_lines_from_chars(first_page)
        # title = _select_title_from_lines(char_lines, first_page.width)
        # if title:
        #     return title

        # fallback cuối
        title = _select_title_from_lines(word_lines, first_page.width)
        logger.warning("[TITLE DEBUG] selected_title=%r", title)
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