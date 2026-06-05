import logging
import re
from typing import Any, Optional

from app.models.canonical_document import CanonicalDocument
from app.services.llm.constants import MAX_INPUT_CHARS

logger = logging.getLogger(__name__)


class LLMInputBuilder:
    def _clean_text(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()

    def _format_page_marker(self, page_number: Any, section: Any = None) -> str:
        page_text = str(page_number).strip() if page_number is not None else "unknown"
        section_text = re.sub(r"\s+", " ", section).strip() if isinstance(section, str) else ""
        if section_text:
            return f"[PAGE {page_text} | SECTION {section_text}]"
        return f"[PAGE {page_text}]"

    def _build_page_aware_text(self, pages: list[dict[str, Any]] | None) -> str:
        if not pages:
            return ""

        parts: list[str] = []
        last_marker: str | None = None

        for page in pages:
            if not isinstance(page, dict):
                continue

            page_number = page.get("page")
            blocks = page.get("blocks")
            if isinstance(blocks, list) and blocks:
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    text = self._clean_text(str(block.get("text") or ""))
                    if not text:
                        continue
                    marker = self._format_page_marker(
                        block.get("page") or page_number,
                        block.get("section"),
                    )
                    if marker != last_marker:
                        parts.append(marker)
                        last_marker = marker
                    parts.append(text)
                continue

            text = self._clean_text(str(page.get("text") or ""))
            if not text:
                continue

            sections = page.get("sections")
            section = sections[0] if isinstance(sections, list) and len(sections) == 1 else None
            marker = self._format_page_marker(page_number, section)
            if marker != last_marker:
                parts.append(marker)
                last_marker = marker
            parts.append(text)

        return "\n\n".join(parts).strip()

    def _extract_priority_tail(self, text: str, fallback_chars: int) -> str:
        """
        Ưu tiên lấy đoạn cuối paper bắt đầu từ các section thường chứa limitation.
        Nếu không tìm thấy thì lấy fallback từ cuối văn bản.
        """
        patterns = [
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?limitations?\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?challenges?\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?open\s+problems?\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?perspectives?\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?outlook\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?future\s+(?:trends?|work|research|direction|outlook|perspective)s?\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?discussion\b",
            r"\n\s*(?:[ivxlcdm\d]+(?:\.[ivxlcdm\d]+)*\.?\s+)?conclusion\b",
        ]

        lowered = text.lower()
        for pattern in patterns:
            m = re.search(pattern, lowered)
            if m:
                tail = text[m.start():]
    # Lấy fallback_chars ký tự ĐẦU TIÊN của đoạn tail này
                return tail[:fallback_chars]

        return text[-fallback_chars:] if len(text) > fallback_chars else text

    def _truncate_for_academic_paper(self, text: str, max_chars: int) -> str:
        """
        Ưu tiên:
        - phần đầu: problem / method / contributions
        - phần cuối: limitations / discussion / conclusion
        - phần giữa: giữ ít hơn, chỉ để có thêm evaluation signals
        """
        if len(text) <= max_chars:
            return text

        head_chars = int(max_chars * 0.50)
        middle_chars = int(max_chars * 0.10)
        tail_chars = int(max_chars * 0.40)

        head = text[:head_chars]

        mid_start = max(0, len(text) // 2 - middle_chars // 2)
        mid_end = mid_start + middle_chars
        middle = text[mid_start:mid_end]

        tail = self._extract_priority_tail(text, tail_chars)

        return (
            head
            + "\n\n[... SKIPPED ...]\n\n"
            + middle
            + "\n\n[... SKIPPED ...]\n\n"
            + tail
        )

    def build(
        self,
        canonical: CanonicalDocument,
        parsed_text: Optional[str] = None,
        full_text: Optional[str] = None,
        pages: list[dict[str, Any]] | None = None,
    ) -> str:
        parts: list[str] = []

        parts.append(
            "### CRITICAL EXTRACTION RULES ###\n"
            "1. Return ONLY a valid JSON object. No conversational text.\n"
            "2. Keep each 'value' concise (usually <= 35 words), but keep core meaning complete.\n"
            "3. CONTRIBUTIONS: Prefer 2-3 atomic items when claims are clearly present.\n"
            "4. LIMITATIONS: Return [] unless the authors explicitly state a limitation, scope constraint, caveat, or future-work item.\n"
            "5. METHOD/CONTRIBUTIONS: Use this paper's own method/results, not cited prior work.\n"
            "6. EVALUATION: Datasets/tasks and metrics must come from experiment context; citation venues are not datasets.\n"
            "7. EVIDENCE: Keep snippet short (<= 180 chars). Use '...' to shorten long quotes.\n"
            "8. Use only provided content. If not found, use null or [].\n"
            "9. When [PAGE ... | SECTION ...] markers are present, use them for evidence page and section."
        )

        parts.append(
            "You are given extracted content from an academic paper. "
            "Use only the provided content. "
            "Do not guess missing information. "
            "If evidence is hard to localize, still keep conservative values grounded in text. "
            "Avoid leaving contributions empty when clear claims exist. "
            "Do not use prior-work or baseline weaknesses from the introduction as limitations of the paper."
        )


        parts.append(
            "You are an academic extractor. Return ONLY JSON.\n"
            "Each evidence snippet must be short and exact.\n"
            "Do not provide long quotations."
        )

        if canonical.title:
            parts.append(f"[TITLE]\n{canonical.title}")

        if canonical.abstract:
            parts.append(f"[ABSTRACT]\n{canonical.abstract}")

        if canonical.title_candidate and canonical.title_candidate != canonical.title:
            parts.append(f"[DETECTED_TITLE_CANDIDATE]\n{canonical.title_candidate}")

        page_aware_text = self._build_page_aware_text(pages)
        effective_text = page_aware_text or (full_text or "").strip() or (parsed_text or "").strip()
        cleaned_text = self._clean_text(effective_text)

        if cleaned_text:
            truncated_text = self._truncate_for_academic_paper(
                cleaned_text,
                MAX_INPUT_CHARS,
            )
            parts.append(f"[PAPER_TEXT]\n{truncated_text}")

        final_text = "\n\n".join(part.strip() for part in parts if part and part.strip())

        logger.info("[LLM INPUT] paper_text_chars=%s", len(cleaned_text))
        logger.info("[LLM INPUT] final_chars=%s", len(final_text))

        return final_text
