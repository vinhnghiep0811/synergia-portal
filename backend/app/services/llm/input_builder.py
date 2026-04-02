import logging
from typing import Optional

from app.models.canonical_document import CanonicalDocument
from app.services.llm.constants import MAX_INPUT_CHARS

logger = logging.getLogger(__name__)

class LLMInputBuilder:
    def build(self, canonical: CanonicalDocument, parsed_text: Optional[str] = None, full_text: Optional[str] = None,) -> str:
        parts: list[str] = []

        parts.append(
            "You are given extracted content from an academic paper. "
            "Use only the provided content."
            "Do not guess missing information. "
            "If evidence is missing, fields must remain null, empty, or unknown."
        )

        if canonical.title:
            parts.append(f"[TITLE]\n{canonical.title}")

        if canonical.abstract:
            parts.append(f"[ABSTRACT]\n{canonical.abstract}")

        if canonical.title_candidate and canonical.title_candidate != canonical.title:
            parts.append(f"[DETECTED_TITLE_CANDIDATE]\n{canonical.title_candidate}")

        effective_text = (full_text or "").strip() or (parsed_text or "").strip()
        if effective_text:
            parts.append(self._format_paper_text(effective_text))
        final_text = "\n\n".join(part.strip() for part in parts if part and part.strip())
        logger.info("[LLM INPUT] paper_text_chars=%s", len(effective_text))
        logger.info("[LLM INPUT] total_chars=%s", len(final_text))
        return final_text[:MAX_INPUT_CHARS]

    def _format_paper_text(self, text: str) -> str:
        cleaned = self._clean_text(text)
        return f"[PAPER_TEXT]\n{cleaned}"
    
    def _clean_text(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()