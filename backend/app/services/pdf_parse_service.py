import hashlib
import re
from typing import Optional, Tuple

import pdfplumber


DOI_REGEX = re.compile(r"(?<![\d.])10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


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
            if page_text.strip():
                texts.append(page_text)

    full_text = "\n".join(texts).strip()
    preview = full_text[:preview_chars] if full_text else ""

    if not full_text:
        raise ValueError("Could not extract text from PDF")

    return full_text, preview


def normalize_doi(raw_doi: str) -> str:
    doi = raw_doi.strip().lower()
    doi = doi.rstrip(").,;:]}")
    return doi


def detect_doi(text: str) -> Optional[str]:
    match = DOI_REGEX.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0))


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return line

def detect_title(file_path: str) -> Optional[str]:
    with pdfplumber.open(file_path) as pdf:
        first_page = pdf.pages[0]
        words = first_page.extract_words(extra_attrs=["size", "fontname"])
        
        if not words:
            return None

        max_size = max(w["size"] for w in words)
        
        title_words = [
            w["text"] for w in words 
            if w["size"] >= (max_size - 0.5) 
            and w["top"] < (first_page.height / 2)
        ]
        
        if not title_words:
            return None
            
        title = " ".join(title_words)
        return re.sub(r"\s+", " ", title).strip()

def normalize_text_for_fingerprint(text: str) -> str:
    text = text.lower()
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