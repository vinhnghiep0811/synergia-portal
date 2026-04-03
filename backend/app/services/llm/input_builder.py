import logging
import re
from typing import Optional

from app.models.canonical_document import CanonicalDocument
from app.services.llm.constants import MAX_INPUT_CHARS

logger = logging.getLogger(__name__)


class LLMInputBuilder:
    def _clean_text(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()

    def _extract_priority_tail(self, text: str, fallback_chars: int) -> str:
        """
        Ưu tiên lấy đoạn cuối paper bắt đầu từ các section thường chứa limitation.
        Nếu không tìm thấy thì lấy fallback từ cuối văn bản.
        """
        patterns = [
            r"\n\s*\d+(\.\d+)?\s+limitations\b",
            r"\n\s*limitations\b",
            r"\n\s*\d+(\.\d+)?\s+discussion\b",
            r"\n\s*discussion\b",
            r"\n\s*\d+(\.\d+)?\s+future work\b",
            r"\n\s*future work\b",
            r"\n\s*\d+(\.\d+)?\s+conclusion\b",
            r"\n\s*conclusion\b",
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
    ) -> str:
        parts: list[str] = []

        parts.append(
            "### CRITICAL EXTRACTION RULES ###\n"
            "1. Return ONLY a valid JSON object. No conversational text.\n"
            "2. Each 'value' must be a single concise sentence (max 20 words).\n"
            "3. LIMITATIONS: Extract max 3 items. Each snippet MUST be < 150 characters.\n"
            "4. EVIDENCE: Each snippet MUST be < 150 characters. Use '...' to shorten long quotes.\n"
            "5. Use only provided content. If not found, use null or []."
        )

        parts.append(
            "You are given extracted content from an academic paper. "
            "Use only the provided content. "
            "Do not guess missing information. "
            "If evidence is missing, fields must remain null, empty, or unknown."
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

        effective_text = (full_text or "").strip() or (parsed_text or "").strip()
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