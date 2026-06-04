import os
import re
import logging
import json
import tempfile
import html
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.canonical_document import CanonicalDocument
from app.models.extraction_run import ExtractionRun
from app.repositories.extraction_run_repository import ExtractionRunRepository
from app.schemas.extraction_result import ExtractionResultSchema
from app.services.llm.input_builder import LLMInputBuilder
from app.services.llm.prompt_builder import LLMPromptBuilder
from app.services.llm_prompt_template_service import LLMPromptTemplateService
from app.services.llm.constants import PROMPT_VERSION
from app.services.llm.provider_factory import LLMProviderFactory
from app.services.pdf_parse_service import extract_pdf_text_for_llm
from app.services.runtime_config_service import RuntimeConfigService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)
REGEX_FALLBACK_MODEL = "deterministic_regex"
PAGE_MATCH_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "those",
    "into",
    "onto",
    "are",
    "was",
    "were",
    "been",
    "being",
    "has",
    "have",
    "had",
    "our",
    "their",
    "its",
    "can",
    "may",
    "will",
    "would",
    "should",
    "could",
    "using",
    "use",
    "used",
    "based",
    "paper",
    "method",
    "model",
    "approach",
}


class LLMExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExtractionRunRepository(db)
        runtime_config = RuntimeConfigService.get(db)
        self.provider = LLMProviderFactory.create(
            provider_name=runtime_config.llm_provider,
            model_name=runtime_config.llm_model,
            retry_limit=runtime_config.pipeline_retry_limit,
            timeout_seconds=runtime_config.pipeline_timeout_seconds,
            api_key=runtime_config.llm_api_key,
            base_url=runtime_config.llm_base_url,
            extra_params=runtime_config.llm_extra_params,
        )
        self.input_builder = LLMInputBuilder()
        prompt_templates = LLMPromptTemplateService(db).get_template_map()
        self.prompt_builder = LLMPromptBuilder(prompt_templates)

    def _has_expected_extraction_schema(self, raw_result: Any) -> bool:
        if not isinstance(raw_result, dict):
            return False

        required_keys = {
            "problem",
            "method",
            "contributions",
            "limitations",
            "evaluation_setup",
        }

        return required_keys.issubset(set(raw_result.keys()))

    def _schema_keys_for_log(self, raw_result: Any) -> str:
        if isinstance(raw_result, dict):
            return ",".join(sorted(raw_result.keys()))
        return type(raw_result).__name__

    def _normalize_free_text(self, value: Any, max_chars: int = 220) -> str | None:
        if not isinstance(value, str):
            return None

        text = re.sub(r"\s+", " ", value).strip()
        if not text:
            return None

        if self._is_placeholder_text(text):
            return None

        if len(text) > max_chars:
            cut = text[:max_chars]
            last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
            if last_stop > 80:
                text = cut[:last_stop].strip()
            else:
                text = cut.strip()

        return text or None

    def _to_string_list(self, value: Any, max_items: int = 3) -> list[str]:
        candidates: list[str] = []

        if isinstance(value, list):
            for item in value:
                normalized = self._normalize_free_text(item, max_chars=180)
                if normalized:
                    candidates.append(normalized)

        elif isinstance(value, dict):
            for k, v in value.items():
                left = self._normalize_free_text(k, max_chars=120)
                right = self._normalize_free_text(v, max_chars=120) if isinstance(v, str) else None
                if left and right:
                    candidates.append(f"{left}: {right}")
                elif left:
                    candidates.append(left)

        else:
            normalized = self._normalize_free_text(value, max_chars=180)
            if normalized:
                candidates.append(normalized)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= max_items:
                break

        return deduped

    def _dedupe_list_items(
        self,
        items: list[dict[str, Any]],
        max_items: int,
    ) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                continue

            value = item.get("value")
            if not isinstance(value, str):
                continue

            key = re.sub(r"\s+", " ", value).strip().lower()
            if not key or key in seen:
                continue

            deduped.append(item)
            seen.add(key)

            if len(deduped) >= max_items:
                break

        return deduped

    def _has_limitation_signal(self, text: str) -> bool:
        lowered = self._normalize_limitation_signal_text(text)
        if not lowered:
            return False

        signal_patterns = [
            r"\blimit(?:ation|ations|ed|s)?\b",
            r"\b(?:future|further) (?:work|research|direction|directions|study|investigation)\b",
            r"\b(?:interesting|promising) directions? for (?:future|further) (?:work|research)\b",
            r"\bwe (?:plan|intend|leave|hope|will investigate|aim) to\b",
            r"\bremain(?:s)? (?:an|a)? ?(?:open )?(?:problem|question|challenge)\b",
            r"\bremain(?:s)?\b.{0,40}\bto be\b.{0,40}\b(?:overcome|solved|addressed|resolved|investigated|studied)\b",
            r"\b(?:constraint|constraints|assumption|assumptions|caveat|caveats|drawback|drawbacks|weakness|weaknesses|shortcoming|shortcomings|obstacle|obstacles|barrier|barriers|bottleneck|bottlenecks|difficulty|difficulties)\b",
            r"\b(?:cannot|can't|unable to|fails? to|struggles? to|does not|do not|did not|is not yet|are not yet|was not yet|were not yet|not yet viable|not yet efficient|not yet practical|may not|might not|not always|not in all cases|not necessarily)\b",
            r"\b(?:difficult|hard|challenging)\s+to\s+(?:scale|generalize|train|evaluate|implement|achieve|obtain|measure)\b",
            r"\b(?:expensive|costly|latency|scalability|memory constraints?|memory consumption|compute cost|computational cost|resource intensive)\b",
            r"\bprecludes? parallelization\b",
            r"\brequires?\b.{0,80}\b(?:human|manual|annotation|labels|labeled|compute|memory|resources?|pretraining|training data)\b",
            r"\b(?:only|solely) (?:evaluated|tested|trained|demonstrated|considered|studied|reported)\b",
            r"\b(?:restricted|confined|limited) to\b",
            r"\bshould not be (?:the )?(?:only|sole) (?:metric|measure|criterion|criteria|evaluation)\b",
            r"\bnot (?:be )?the only (?:metric|measure|criterion|criteria|evaluation)\b",
            r"\b(?:metric|measure|criterion|criteria|evaluation)\b.{0,100}\b(?:shortcomings?|limitations?|insufficient|not enough)\b",
            r"\b(?:can|could|may|might) be (?:extended|applied|adapted|tested|evaluated|investigated|explored)\b.{0,120}\b(?:future|further|additional|other|new)\b",
        ]

        return any(re.search(pattern, lowered) for pattern in signal_patterns)

    def _is_prior_work_context(self, text: str) -> bool:
        lowered = self._normalize_limitation_signal_text(text)
        if not lowered:
            return False

        prior_markers = [
            r"\bprior work\b",
            r"\bprevious work\b",
            r"\bexisting (?:work|methods?|models?|approaches?)\b",
            r"\bbaseline(?:s)?\b",
            r"\btraditional (?:methods?|models?|approaches?)\b",
            r"\brecurrent neural networks?\b",
            r"\brecurrent models?\b",
            r"\bconvolutional neural networks?\b",
            r"\bauto-?regressive property\b",
            r"\bprevious hidden states?\b",
            r"\bcurrent time step\b",
            r"\bsequential nature\b",
            r"\bprecludes? parallelization\b",
        ]
        current_scope_markers = [
            r"\bwe\b",
            r"\bour\b",
            r"\bthis (?:paper|work|study)\b",
            r"\bproposed\b",
            r"\btransformer\b",
            r"\bfuture (?:work|research|direction|directions)\b",
            r"\bfurther (?:work|research|direction|directions)\b",
        ]

        has_prior_marker = any(re.search(pattern, lowered) for pattern in prior_markers)
        has_current_scope_marker = any(re.search(pattern, lowered) for pattern in current_scope_markers)
        return has_prior_marker and not has_current_scope_marker

    def _normalize_limitation_signal_text(self, text: Any) -> str:
        if not isinstance(text, str):
            return ""

        repaired = self._repair_joined_extraction_text(text)
        return re.sub(r"\s+", " ", repaired.lower()).strip()

    @staticmethod
    def _normalize_section_label(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        normalized = value.replace("\u00a0", " ").strip().lower()
        normalized = re.sub(r"^#+\s*", "", normalized)
        normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip(" .:-")

    def _is_allowed_limitation_section(self, section: Any) -> bool:
        normalized = self._normalize_section_label(section)
        if not normalized:
            return False

        return bool(
            re.search(
                r"\b("
                r"limitations?|"
                r"discussion|"
                r"conclusions?|"
                r"future work|"
                r"threats? to validity|"
                r"caveats?|"
                r"outlook"
                r")\b",
                normalized,
            )
        )

    def _is_rejected_limitation_section(self, section: Any) -> bool:
        normalized = self._normalize_section_label(section)
        if not normalized:
            return False

        return bool(
            re.search(
                r"\b("
                r"abstract|"
                r"introduction|"
                r"motivation|"
                r"background|"
                r"related work|"
                r"prior work|"
                r"method(?:s|ology)?|"
                r"approach(?:es)?|"
                r"model|"
                r"architecture|"
                r"experiment(?:s)?|"
                r"evaluation|"
                r"results?|"
                r"references?|"
                r"bibliography|"
                r"appendix"
                r")\b",
                normalized,
            )
        )

    def _section_from_marker_line(self, line: str) -> str | None:
        marker_match = re.fullmatch(
            r"\[PAGE\s+[^\]|]+(?:\s*\|\s*SECTION\s+([^\]]+))?\]",
            line.strip(),
            flags=re.IGNORECASE,
        )
        if marker_match:
            section = self._normalize_section_label(marker_match.group(1))
            return section or None

        tag_match = re.fullmatch(r"\[(ABSTRACT|PAPER_TEXT)\]", line.strip(), flags=re.IGNORECASE)
        if tag_match:
            tag = tag_match.group(1).lower()
            return "abstract" if tag == "abstract" else None

        return None

    def _section_from_heading_line(self, line: str) -> str | None:
        stripped = re.sub(r"\s+", " ", (line or "").strip())
        if not stripped or stripped.startswith("["):
            return None

        candidate = re.sub(r"^#+\s*", "", stripped).strip()
        candidate = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", candidate).strip()
        candidate = candidate.strip(" .:-")
        normalized = self._normalize_section_label(candidate)
        if not normalized or len(normalized) > 90:
            return None

        known_heading_patterns = [
            r"abstract",
            r"introduction",
            r"motivation",
            r"background",
            r"related work",
            r"prior work",
            r"method(?:s|ology)?",
            r"approach(?:es)?",
            r"model(?: architecture)?",
            r"architecture",
            r"experiment(?:s)?",
            r"experimental setup",
            r"evaluation",
            r"results?",
            r"discussion",
            r"conclusions?",
            r"future work",
            r"limitations?",
            r"limitations? and future work",
            r"threats? to validity",
            r"caveats?",
            r"outlook",
            r"references?",
            r"bibliography",
            r"appendix",
        ]

        if any(re.fullmatch(pattern, normalized) for pattern in known_heading_patterns):
            return normalized

        return None

    def _section_chunks_from_input_text(self, input_text: str) -> list[dict[str, Any]]:
        if not isinstance(input_text, str) or not input_text.strip():
            return []

        chunks: list[dict[str, Any]] = []
        current_section: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_lines
            if not current_lines:
                return
            text = "\n".join(current_lines).strip()
            if text:
                chunks.append({"section": current_section, "text": text})
            current_lines = []

        for line in input_text.splitlines():
            tag_match = re.fullmatch(r"\[(ABSTRACT|PAPER_TEXT)\]", line.strip(), flags=re.IGNORECASE)
            if tag_match:
                flush()
                current_section = "abstract" if tag_match.group(1).lower() == "abstract" else None
                current_lines.append(line)
                continue

            marker_section = self._section_from_marker_line(line)
            heading_section = marker_section or self._section_from_heading_line(line)
            if heading_section is not None:
                flush()
                current_section = heading_section
            current_lines.append(line)

        flush()
        return chunks

    def _infer_section_for_snippet_from_input_text(
        self,
        snippet: str,
        input_text: str,
    ) -> str | None:
        normalized_snippet = self._normalize_text_for_page_match(snippet)
        if not normalized_snippet:
            return None

        snippet_words = normalized_snippet.split()
        snippet_tokens = self._significant_match_tokens(normalized_snippet)
        best_section: str | None = None
        best_score = 0.0

        for chunk in self._section_chunks_from_input_text(input_text):
            normalized_chunk = self._normalize_text_for_page_match(chunk.get("text") or "")
            if not normalized_chunk:
                continue

            score = 0.0
            if normalized_snippet in normalized_chunk:
                score = 1.0
            elif self._contains_token_window(normalized_chunk, snippet_words):
                score = 0.92
            elif len(snippet_tokens) >= 4:
                chunk_tokens = set(normalized_chunk.split())
                overlap = sum(1 for token in snippet_tokens if token in chunk_tokens)
                score = overlap / len(snippet_tokens)

            if score > best_score:
                best_score = score
                best_section = chunk.get("section")

        return best_section if best_score >= 0.75 else None

    def _limitation_has_allowed_source_context(
        self,
        item: dict[str, Any],
        input_text: str,
    ) -> bool:
        evidence = item.get("evidence")
        evidence_items = evidence if isinstance(evidence, list) else []

        snippets = [
            ev.get("snippet")
            for ev in evidence_items
            if isinstance(ev, dict) and isinstance(ev.get("snippet"), str)
        ]
        value = item.get("value")
        if isinstance(value, str):
            snippets.append(value)

        # Check if the document has any explicitly allowed limitation sections.
        # If it does, we enforce strict whitelist-matching.
        # If it does not, we allow limitations as long as they are not explicitly in rejected/blacklisted sections.
        has_any_allowed_section = False
        if isinstance(input_text, str) and input_text.strip():
            for chunk in self._section_chunks_from_input_text(input_text):
                if self._is_allowed_limitation_section(chunk.get("section")):
                    has_any_allowed_section = True
                    break

        if isinstance(input_text, str) and input_text.strip():
            for snippet in snippets:
                section = self._infer_section_for_snippet_from_input_text(snippet, input_text)
                if self._is_allowed_limitation_section(section):
                    return True
                if self._is_rejected_limitation_section(section):
                    return False

        for ev in evidence_items:
            if not isinstance(ev, dict):
                continue
            section = ev.get("section")
            if self._is_allowed_limitation_section(section):
                return True
            if self._is_rejected_limitation_section(section):
                return False

        if not isinstance(input_text, str) or not input_text.strip():
            return True

        if not has_any_allowed_section:
            return True

        return False

    def _filter_limitations_by_source_context(
        self,
        limitations: Any,
        input_text: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(limitations, list):
            return []

        filtered: list[dict[str, Any]] = []
        for item in limitations:
            if not isinstance(item, dict):
                continue
            if not self._limitation_has_allowed_source_context(item, input_text):
                logger.info(
                    "[LLM NORMALIZE] Dropping limitation outside allowed source context: %s",
                    self._normalize_free_text(item.get("value"), max_chars=120),
                )
                continue
            filtered.append(item)

        return filtered

    def _is_valid_limitation_item(self, item: dict[str, Any], is_fallback: bool = False) -> bool:
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            return False

        evidence = item.get("evidence")
        evidence_text = " ".join(
            ev.get("snippet", "")
            for ev in evidence
            if isinstance(ev, dict) and isinstance(ev.get("snippet"), str)
        ) if isinstance(evidence, list) else ""

        combined = re.sub(r"\s+", " ", f"{value} {evidence_text}").strip()
        if self._is_noisy_extraction_sentence(combined):
            return False

        lowered = combined.lower()

        # If it is direct LLM output, we don't apply strict semantic signal filters!
        if not is_fallback:
            if self._is_prior_work_context(combined):
                return False
            return True

        # If it is fallback (coerced from raw text), we enforce strict signals!
        if re.match(
            r"^#+\s*\d*(?:\.\d+)?\s*(abstract|introduction|background|related work|method|approach|experiments?|results?)\b",
            lowered,
        ):
            return False

        if not self._has_limitation_signal(combined):
            return False

        if self._is_prior_work_context(combined):
            return False

        positive_only_markers = [
            "state of the art",
            "state-of-the-art",
            "we propose",
            "we present",
            "we introduce",
            "we achieve",
            "outperform",
        ]
        if any(marker in lowered for marker in positive_only_markers) and not re.search(
            r"\b(?:however|although|but|future|limit|cannot|unable|fails?|requires?|only|restricted|confined)\b",
            lowered,
        ):
            return False

        return True

    def _normalize_limitations_field(self, raw: Any, is_fallback: bool = False) -> list[dict[str, Any]]:
        candidates = self._normalize_list_field(raw, max_items=6)
        filtered = [item for item in candidates if self._is_valid_limitation_item(item, is_fallback=is_fallback)]
        return self._dedupe_list_items(filtered, max_items=2)

    @staticmethod
    def _repair_joined_extraction_text(text: str) -> str:
        if not isinstance(text, str):
            return ""

        repaired = text
        repaired = repaired.replace("\u2019", "'").replace("`", "'")
        repaired = re.sub(r"^(?:one-sentence summary|summary|abstract|introduction):\s*", "", repaired, flags=re.IGNORECASE)
        repaired = re.sub("[\u2010-\u2015]", "-", repaired)
        repaired = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", repaired)
        joined_we_verbs = (
            "propose|present|introduce|replace|achieve|show|report|benchmark|"
            "evaluate|test|analyze|analyse|demonstrate|find|obtain|develop|"
            "train|review|discuss|explore|describe|use|found|plan|improve"
        )
        repaired = re.sub(
            rf"\b([Ww]e)({joined_we_verbs})\b",
            r"\1 \2",
            repaired,
        )
        repaired = re.sub(
            r"\b([Oo]ur)(model|method|architecture|approach|network|proposed|results?|experiments?)\b",
            r"\1 \2",
            repaired,
        )
        repaired = re.sub(r"\b([Tt]his)(paper|work|study)\b", r"\1 \2", repaired)
        repaired = re.sub(r"\b([Ii]n)(this)(work|paper)\b", r"\1 \2 \3", repaired)
        repaired = re.sub(r"\b([Ii]n)(future)\b", r"\1 \2", repaired)
        repaired = re.sub(
            r"\b(to)(investigate|extend|explore|study|address|improve)\b",
            r"\1 \2",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(r"\b(?!Metal\b)([A-Z])etal\.?(?=\W|$)", r"\1 et al.", repaired)
        repaired = re.sub(r"(?<=[,;:])(?=[A-Za-z])", " ", repaired)
        return repaired

    def _has_current_paper_signal(self, text: str) -> bool:
        lowered = self._repair_joined_extraction_text(text).lower()
        signal_patterns = [
            (
                r"\bwe\s+(?:propose|present|introduce|replace|achieve|show|report|"
                r"benchmark|evaluate|test|analyze|analyse|demonstrate|find|obtain|"
                r"develop|train|review|discuss|explore|describe|use|improve)\b"
            ),
            r"\bin this (?:work|paper|study)\b",
            r"\bour (?:model|method|architecture|approach|network|proposed|experiments?|results?)\b",
            (
                r"\b(?:this|the) (?:paper|work|study) (?:aims|proposes|presents|"
                r"introduces|reports|shows|evaluates|tests|analyzes|analyses|"
                r"demonstrates|finds|trains|reviews|discusses|explores|describes)\b"
            ),
        ]
        return any(re.search(pattern, lowered) for pattern in signal_patterns)

    def _is_external_work_statement(self, text: str) -> bool:
        lowered = self._repair_joined_extraction_text(text).lower()
        if self._has_current_paper_signal(lowered):
            return False

        external_patterns = [
            r"\b[a-z][a-z-]+ et al\.?\s*(?:\(\d{4}\))?",
            r"\b(?:vaswani|sutskever|bahdanau|luong|wu|gehring|kaiser|sennrich)\b",
            r"\b(?:previous|prior|existing|baseline|original) (?:work|model|method|architecture|approach|network)\b",
            r"^while the proposed (?:architecture|model|method|approach|network)\b",
        ]
        return any(re.search(pattern, lowered) for pattern in external_patterns)

    def _is_noisy_extraction_sentence(self, text: str) -> bool:
        lowered = re.sub(r"\s+", " ", (text or "").lower()).strip()
        if not lowered:
            return True

        if len(lowered.split()) < 4:
            return True

        if "@" in lowered or "proceedings of" in lowered or "arxiv:" in lowered:
            return True

        # Filter out email addresses
        if re.search(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", lowered):
            return True

        # Filter out typical affiliation/author headers
        affiliation_keywords = [
            "department of", "dept. of", "university of", "univ. of",
            "institute for", "institute of", "inst. of", "laboratory of",
            "corporation", "co., ltd.", "inc.", "gmbh", "postal code",
            "zip code", "e-mail:", "email:", "authors:", "correspondence to:",
            "all rights reserved", "copyright", "associated with", "reprint"
        ]
        if any(keyword in lowered for keyword in affiliation_keywords):
            return True

        # Filter out figure/table/equation references
        if re.match(r"^(?:fig(?:ure)?|table|eq(?:uation)?)\b\s*\d+", lowered):
            return True

        if re.match(r"^\[page \d+\]", lowered) and not self._has_current_paper_signal(lowered):
            return True

        if " abstract " in f" {lowered} " and not self._has_current_paper_signal(lowered):
            return True

        if re.match(r"^#+\s*\d*(?:\.\d+)?\s*(references|appendix)\b", lowered):
            return True

        return False

    def _is_valid_method_sentence(self, text: str) -> bool:
        lowered = self._repair_joined_extraction_text(text).lower()
        if self._is_noisy_extraction_sentence(lowered):
            return False
        if self._is_external_work_statement(lowered):
            return False

        method_patterns = [
            r"\bwe\s+(?:propose|present|introduce|develop|replace|use)\b",
            r"\bin this (?:work|paper),?\s+we\s+(?:propose|present|introduce|develop)\b",
            r"\bour (?:model|method|architecture|approach|network)\b",
        ]
        return any(re.search(pattern, lowered) for pattern in method_patterns)

    def _is_valid_contribution_sentence(self, text: str) -> bool:
        lowered = self._repair_joined_extraction_text(text).lower()
        if self._is_noisy_extraction_sentence(lowered):
            return False
        if self._is_external_work_statement(lowered):
            return False

        has_claim_owner = (
            self._has_current_paper_signal(lowered)
            or re.search(
                r"\b(?:weighted transformer|fast-forward|f-f connections?|deep-att|deep-ed|our|proposed)\b",
                lowered,
            )
        )
        if not has_claim_owner:
            return False

        contribution_patterns = [
            (
                r"\bwe\s+(?:propose|present|introduce|develop|replace|show|report|"
                r"achieve|obtain|improve|outperform|benchmark|evaluate|test|"
                r"analyze|analyse|demonstrate|find|train|review|discuss|explore|"
                r"describe)\b"
            ),
            r"\bour (?:model|method|architecture|approach|network|results?)\b",
            r"\bthe proposed (?:model|method|architecture|approach|network)\b",
            (
                r"\b(?:this|the) (?:paper|work|study) (?:aims|proposes|presents|"
                r"introduces|reports|shows|evaluates|tests|analyzes|analyses|"
                r"demonstrates|finds|trains|reviews|discusses|explores|describes)\b"
            ),
            r"\b(?:achieves?|improves?|outperforms?|converges?)\b.{0,80}\b(?:bleu|accuracy|f1|state-of-the-art|baseline)\b",
        ]
        return any(re.search(pattern, lowered) for pattern in contribution_patterns)

    def _pick_method_sentence(self, sentences: list[str]) -> str | None:
        for sentence in sentences:
            if self._is_valid_method_sentence(sentence):
                return sentence
        return None

    def _pick_contribution_sentences(self, sentences: list[str], max_items: int = 3) -> list[str]:
        candidates: list[str] = []
        seen_token_sets: list[set[str]] = []
        for sentence in sentences:
            if not self._is_valid_contribution_sentence(sentence):
                continue

            cleaned = re.sub(r"\s+", " ", sentence).strip()
            tokens = {
                token
                for token in re.findall(r"[a-z0-9]+", cleaned.lower())
                if len(token) > 3 and token not in PAGE_MATCH_STOPWORDS
            }
            if tokens and any(
                len(tokens & seen) / max(1, min(len(tokens), len(seen))) >= 0.72
                for seen in seen_token_sets
            ):
                continue

            candidates.append(sentence)
            seen_token_sets.append(tokens)
            if len(candidates) >= max_items:
                break

        return candidates

    def _normalize_method_field(self, raw: Any) -> dict[str, Any]:
        field = self._normalize_scalar_field(raw)
        value = field.get("value")
        if not isinstance(value, str) or not value.strip():
            return field

        if self._is_noisy_extraction_sentence(value) or self._is_external_work_statement(value):
            return {"value": None, "evidence": []}

        return field

    def _is_valid_contribution_item(self, item: dict[str, Any], is_fallback: bool = False) -> bool:
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            return False

        evidence = item.get("evidence")
        evidence_text = " ".join(
            ev.get("snippet", "")
            for ev in evidence
            if isinstance(ev, dict) and isinstance(ev.get("snippet"), str)
        ) if isinstance(evidence, list) else ""

        combined = re.sub(r"\s+", " ", f"{value} {evidence_text}").strip()
        if self._is_noisy_extraction_sentence(combined):
            return False

        # If it is direct LLM output, we don't apply strict semantic signal filters!
        if not is_fallback:
            if self._is_external_work_statement(combined):
                return False
            return True

        # If it is fallback (coerced from raw text), we enforce strict signals!
        if self._is_external_work_statement(combined):
            return False
        if self._is_valid_contribution_sentence(combined):
            return True

        lowered = self._repair_joined_extraction_text(combined).lower()
        has_claim_owner = (
            self._has_current_paper_signal(lowered)
            or re.search(
                r"\b(?:weighted transformer|fast-forward|f-f connections?|deep-att|deep-ed|our|proposed)\b",
                lowered,
            )
        )
        if has_claim_owner:
            return True

        # Relaxed check for LLM-extracted items or statements with strong contribution verbs
        contribution_verbs_pattern = (
            r"\b(?:propos|present|introduc|develop|replac|show|report|achiev|"
            r"obtain|improv|outperform|benchmark|evaluat|test|analy[sz]|"
            r"demonstrat|find|found|observ|realis|realiz|train|review|discuss|explor|describ|construct|build)e?d?s?(?:ing)?\b"
        )
        if re.search(contribution_verbs_pattern, lowered):
            return True

        return False

    def _normalize_contributions_field(self, raw: Any, is_fallback: bool = False) -> list[dict[str, Any]]:
        candidates = self._normalize_list_field(raw, max_items=8)
        filtered = [item for item in candidates if self._is_valid_contribution_item(item, is_fallback=is_fallback)]

        deduped: list[dict[str, Any]] = []
        seen_token_sets: list[set[str]] = []
        for item in filtered:
            value = item.get("value", "")
            tokens = {
                token
                for token in re.findall(r"[a-z0-9]+", value.lower())
                if len(token) > 3 and token not in PAGE_MATCH_STOPWORDS
            }
            if tokens and any(
                len(tokens & seen) / max(1, min(len(tokens), len(seen))) >= 0.72
                for seen in seen_token_sets
            ):
                continue

            deduped.append(item)
            seen_token_sets.append(tokens)
            if len(deduped) >= 3:
                break

        return deduped

    def _extract_metrics_from_text(self, text: str) -> list[str]:
        if not text:
            return []

        keywords = [
            ("bleu", "BLEU"),
            ("rouge", "ROUGE"),
            ("f1", "F1"),
            ("accuracy", "accuracy"),
            ("precision", "precision"),
            ("recall", "recall"),
            ("map", "mAP"),
            ("mrr", "MRR"),
            ("meteor", "METEOR"),
            ("ter", "TER"),
            ("perplexity", "perplexity"),
            ("ppl", "PPL"),
            ("carrier mobility", "carrier mobility"),
            ("carrier concentration", "carrier concentration"),
            ("shubnikov-de haas oscillation amplitude", "Shubnikov-de Haas oscillation amplitude"),
            ("shubnikov de haas oscillation amplitude", "Shubnikov-de Haas oscillation amplitude"),
            ("resistivity", "resistivity"),
            ("hall coefficient", "Hall coefficient"),
        ]

        normalized = re.sub(r"[\u2010-\u2015]", "-", text.lower())
        metrics: list[str] = []
        for needle, label in keywords:
            if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", normalized):
                metrics.append(label)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in metrics:
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= 5:
                break

        return deduped

    @staticmethod
    def _split_markdown_table_row(line: str) -> list[str]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return []

        stripped = stripped.strip("|")
        return [
            re.sub(r"\s+", " ", html.unescape(cell).strip())
            for cell in stripped.split("|")
        ]

    @staticmethod
    def _is_markdown_separator_row(cells: list[str]) -> bool:
        non_empty_cells = [cell.strip() for cell in cells if cell.strip()]
        if not non_empty_cells:
            return False
        return all(re.fullmatch(r":?-{3,}:?", cell) for cell in non_empty_cells)

    @staticmethod
    def _is_benchmark_table_header(value: str) -> bool:
        normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
        return bool(
            re.search(
                r"\b(model|models|parser|parsers|system|systems|method|methods|architecture|architectures|baseline|baselines)\b",
                normalized,
            )
        )

    @staticmethod
    def _normalize_benchmark_name(value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = html.unescape(value)
        normalized = normalized.replace("`", "")
        normalized = re.sub(r"[*_]+", "", normalized)
        normalized = re.sub(r"\s*\[[^\]]+\]", "", normalized)
        normalized = re.sub(r"\s*&\s*", " & ", normalized)
        normalized = re.sub(r"\bet\s+al\b\.?", "et al.", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" :-–—\t\r\n")

        if not normalized or len(normalized) > 100:
            return None

        lowered = normalized.lower()
        generic_exact = {
            "baseline",
            "baselines",
            "baseline system",
            "baseline model",
            "baseline method",
            "state-of-the-art",
            "state of the art",
            "state-of-the-art baseline",
            "state of the art baseline",
            "smt system",
            "encoder-decoder baseline",
            "encoder decoder baseline",
            "existing method",
            "existing model",
            "existing system",
            "existing approach",
            "previous method",
            "previous model",
            "previous system",
            "prior work",
            "competitive model",
            "competitive models",
            "best model",
            "best results",
            "single model",
            "ensemble",
            "ensembles",
        }
        if lowered in generic_exact:
            return None

        generic_patterns = [
            r"^(?:previously reported|previous|existing|prior|competing|competitive)\s+(?:models?|methods?|systems?|approaches?)$",
            r"^(?:best|strong|standard)\s+(?:models?|methods?|systems?|baselines?|results?)$",
            r"^(?:the\s+)?(?:literature|prior work|related work)$",
        ]
        if any(re.search(pattern, lowered) for pattern in generic_patterns):
            return None

        if not re.search(r"[A-Za-z]", normalized):
            return None

        digit_count = sum(ch.isdigit() for ch in normalized)
        if digit_count > len(normalized) * 0.45:
            return None

        return normalized

    def _extract_benchmarks_from_markdown_tables(self, text: str) -> list[str]:
        candidates: list[str] = []
        lines = text.splitlines()
        index = 0

        while index < len(lines):
            if not lines[index].lstrip().startswith("|"):
                index += 1
                continue

            table_rows: list[list[str]] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                cells = self._split_markdown_table_row(lines[index])
                if cells:
                    table_rows.append(cells)
                index += 1

            if len(table_rows) < 2:
                continue

            separator_index = next(
                (
                    row_index
                    for row_index, cells in enumerate(table_rows)
                    if self._is_markdown_separator_row(cells)
                ),
                None,
            )
            if separator_index is None or separator_index == 0:
                continue

            header = table_rows[separator_index - 1]
            first_header = next((cell for cell in header if cell.strip()), "")
            if not self._is_benchmark_table_header(first_header):
                continue

            for row in table_rows[separator_index + 1:]:
                if not row:
                    continue
                first_cell = row[0].strip()
                benchmark = self._normalize_benchmark_name(first_cell)
                if benchmark:
                    candidates.append(benchmark)

        return self._dedupe_strings(candidates, max_items=3)

    def _extract_benchmarks_from_text(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        return self._extract_benchmarks_from_markdown_tables(text)

    @staticmethod
    def _dedupe_strings(values: list[str], max_items: int) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue

            normalized = re.sub(r"\s+", " ", value).strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue

            deduped.append(normalized)
            seen.add(key)
            if len(deduped) >= max_items:
                break

        return deduped

    def _has_meaningful_expected_payload(self, raw_result: dict[str, Any]) -> bool:
        problem = (((raw_result.get("problem") or {}).get("value")) if isinstance(raw_result.get("problem"), dict) else None)
        method = (((raw_result.get("method") or {}).get("value")) if isinstance(raw_result.get("method"), dict) else None)
        contributions = raw_result.get("contributions") or []
        limitations = raw_result.get("limitations") or []
        evaluation = ((raw_result.get("evaluation_setup") or {}).get("value") if isinstance(raw_result.get("evaluation_setup"), dict) else None) or {}

        if isinstance(problem, str) and problem.strip():
            return True
        if isinstance(method, str) and method.strip():
            return True
        if isinstance(contributions, list) and len(contributions) > 0:
            return True
        if isinstance(limitations, list) and len(limitations) > 0:
            return True

        if isinstance(evaluation, dict):
            datasets = evaluation.get("datasets") or []
            metrics = evaluation.get("metrics") or []
            benchmarks = evaluation.get("benchmarks") or []
            return bool(datasets or metrics or benchmarks)

        return False

    def _coerce_unexpected_schema_to_expected(self, raw_result: Any) -> dict[str, Any] | None:
        if not isinstance(raw_result, dict):
            return None

        main = raw_result.get("main") if isinstance(raw_result.get("main"), dict) else {}

        abstract = self._normalize_free_text(raw_result.get("abstract"), max_chars=260)
        introduction = self._normalize_free_text(raw_result.get("introduction"), max_chars=260)
        discussion = self._normalize_free_text(raw_result.get("discussion"), max_chars=260)

        methods = self._to_string_list(main.get("methods"), max_items=3)
        result_items = self._to_string_list(main.get("results"), max_items=3)

        problem_value = abstract or introduction
        method_value = methods[0] if methods else self._normalize_free_text(main.get("method"), max_chars=220)

        contributions_values: list[str] = []
        for item in methods + result_items:
            if item not in contributions_values:
                contributions_values.append(item)
            if len(contributions_values) >= 3:
                break

        limitations_values: list[str] = []
        if discussion and self._is_valid_limitation_item({"value": discussion, "evidence": []}):
            limitations_values.append(discussion)

        datasets: list[str] = []
        results_obj = main.get("results")
        if isinstance(results_obj, dict):
            for key in results_obj.keys():
                dataset = self._normalize_free_text(key, max_chars=80)
                if dataset and dataset not in datasets:
                    datasets.append(dataset)
                if len(datasets) >= 3:
                    break

        merged_text = " ".join([x for x in [abstract, introduction, discussion] if isinstance(x, str) and x])
        metrics = self._extract_metrics_from_text(merged_text)

        coerced = {
            "problem": {
                "value": problem_value,
                "evidence": [],
            },
            "method": {
                "value": method_value,
                "evidence": [],
            },
            "contributions": [
                {
                    "value": x,
                    "evidence": [],
                }
                for x in contributions_values
            ],
            "limitations": [
                {
                    "value": x,
                    "evidence": [],
                }
                for x in limitations_values
            ],
            "evaluation_setup": {
                "value": {
                    "datasets": datasets,
                    "metrics": metrics,
                    "benchmarks": [],
                },
                "evidence": [],
            },
        }

        if not self._has_meaningful_expected_payload(coerced):
            return None

        return coerced

    def _extract_tag_block(self, input_text: str, tag: str) -> str:
        if not isinstance(input_text, str) or not input_text.strip():
            return ""

        pattern = rf"\[{re.escape(tag)}\]\n(.*?)(?=\n\[[A-Z_]+\]\n|\Z)"
        match = re.search(pattern, input_text, flags=re.DOTALL)
        if not match:
            return ""

        return re.sub(r"\s+", " ", match.group(1)).strip()

    def _split_sentences(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        repaired = self._repair_joined_extraction_text(text)
        parts = re.split(r"(?<=[.!?])\s+", repaired)
        sentences: list[str] = []
        for part in parts:
            subparts = [part]
            claim_pattern = (
                r"\b(?:in this (?:work|paper|study)|"
                r"we\s+(?:propose|present|introduce|replace|achieve|show|report|benchmark|evaluate|obtain|develop|improve)|"
                r"our\s+(?:model|method|architecture|approach|network|results?))\b"
            )
            for match in re.finditer(claim_pattern, part, flags=re.IGNORECASE):
                if match.start() > 0:
                    subparts.append(part[match.start():])

            for subpart in subparts:
                normalized = self._normalize_free_text(subpart, max_chars=220)
                if normalized:
                    sentences.append(normalized)

        return sentences

    def _pick_sentence_by_keywords(self, sentences: list[str], keywords: list[str]) -> str | None:
        for sentence in sentences:
            lowered = sentence.lower()
            if any(keyword in lowered for keyword in keywords):
                return sentence
        return None

    @staticmethod
    def _is_valid_dataset_name(value: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False

        normalized = re.sub(r"\s+", " ", value).strip()
        lowered = normalized.lower()
        rejected = {
            "acl",
            "emnlp",
            "naacl",
            "nips",
            "neurips",
            "iclr",
            "icml",
            "cvpr",
            "proceedings",
            "dataset",
            "datasets",
            "benchmark",
            "benchmarks",
            "training data",
            "test data",
            "test set",
            "validation set",
            "experiments",
            "experimental results",
        }
        if any(lowered == item or lowered.startswith(f"{item} ") for item in rejected):
            return False

        if not re.search(r"[A-Za-z]", normalized):
            return False

        if len(normalized) > 100:
            return False

        digit_count = sum(ch.isdigit() for ch in normalized)
        if digit_count > len(normalized) * 0.45:
            return False

        accepted_patterns = [
            r"\bwmt\b",
            r"\bnewstest\b",
            r"\bimagenet\b",
            r"\bcoco\b",
            r"\bsquad\b",
            r"\bglue\b",
            r"\bmnli\b",
            r"\bcifar\b",
            r"\blibrispeech\b",
            r"\bwikitext\b",
            r"\beuroparl\b",
            r"\bcommon crawl\b",
            r"\bnews commentary\b",
            r"\bgigaword\b",
            r"\bun\b",
        ]
        if any(re.search(pattern, lowered) for pattern in accepted_patterns):
            return True

        has_named_dataset_signal = (
            re.search(r"\b(?:dataset|corpus|benchmark|testbed|cohort|registry)\b", lowered)
            or re.search(r"[A-Z]{2,}", normalized)
            or re.search(r"\d", normalized)
        )
        return bool(has_named_dataset_signal)

    @staticmethod
    def _normalize_metric_name(value: str) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None

        normalized = html.unescape(value)
        normalized = normalized.replace("`", "")
        normalized = re.sub(r"[\u2010-\u2015]", "-", normalized)
        normalized = re.sub(r"[*_]+", "", normalized)
        normalized = re.sub(r"\s*\[[^\]]+\]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" :-\t\r\n")
        if not normalized or len(normalized) > 90:
            return None

        lowered = normalized.lower()
        metric_map = {
            "bleu": "BLEU",
            "bleu score": "BLEU",
            "rouge": "ROUGE",
            "f1": "F1",
            "accuracy": "accuracy",
            "precision": "precision",
            "recall": "recall",
            "map": "mAP",
            "mrr": "MRR",
            "meteor": "METEOR",
            "ter": "TER",
            "perplexity": "perplexity",
            "ppl": "PPL",
        }
        for key, label in metric_map.items():
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", lowered):
                return label

        generic_exact = {
            "metric",
            "metrics",
            "evaluation",
            "performance",
            "score",
            "scores",
            "result",
            "results",
            "measurement",
            "measurements",
            "value",
            "values",
            "benchmark",
            "benchmarks",
            "dataset",
            "datasets",
            "table",
            "figure",
        }
        if lowered in generic_exact:
            return None

        generic_patterns = [
            r"^(?:various|several|multiple|standard|common|reported)\s+(?:metrics?|measurements?|scores?)$",
            r"^(?:experimental|evaluation|performance)\s+(?:metrics?|results?|scores?)$",
            r"^(?:the\s+)?(?:main|primary|overall)\s+(?:metric|measure|score)$",
        ]
        if any(re.search(pattern, lowered) for pattern in generic_patterns):
            return None

        if not re.search(r"[A-Za-z]", normalized):
            return None

        digit_count = sum(ch.isdigit() for ch in normalized)
        if digit_count > len(normalized) * 0.45:
            return None

        return normalized

    def _extract_datasets_from_text(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        repaired = self._repair_joined_extraction_text(text)
        candidates: list[str] = []

        language_pair = r"English\s*(?:-|to)?\s*to\s*(?:German|French|Czech|Romanian)|English-to-(?:German|French|Czech|Romanian)"
        for match in re.finditer(
            rf"\bWMT'?\s*(?:19|20)?(\d{{2}}|\d{{4}})(?:\s+({language_pair}))?",
            repaired,
            flags=re.IGNORECASE,
        ):
            year = match.group(1)
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"

            pair = match.group(2)
            if pair:
                pair_match = re.search(
                    r"English\s*-?\s*to\s*-?\s*(German|French|Czech|Romanian)",
                    pair,
                    flags=re.IGNORECASE,
                )
                if pair_match:
                    candidates.append(f"WMT {year} English-to-{pair_match.group(1).title()}")
                else:
                    candidates.append(f"WMT {year}")
            else:
                candidates.append(f"WMT {year}")

        for match in re.finditer(r"\bWMT'?\s*(?:19|20)?(\d{2}|\d{4})", repaired, flags=re.IGNORECASE):
            year = match.group(1)
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"
            window = repaired[match.start():match.start() + 260]
            for language in ["German", "French", "Czech", "Romanian"]:
                if re.search(rf"English\s*-?\s*to\s*-?\s*{language}", window, flags=re.IGNORECASE):
                    candidates.append(f"WMT {year} English-to-{language}")

        for match in re.finditer(r"\bnewstest\s*[- ]?\s*(\d{4})\b", repaired, flags=re.IGNORECASE):
            candidates.append(f"newstest {match.group(1)}")

        known_dataset_tokens = [
            "ImageNet",
            "COCO",
            "SQuAD",
            "GLUE",
            "MNLI",
            "CIFAR-10",
            "CIFAR-100",
            "LibriSpeech",
            "WikiText",
            "Europarl",
            "Common Crawl",
            "News Commentary",
            "Gigaword",
        ]

        lowered = repaired.lower()
        for token in known_dataset_tokens:
            if token.lower() in lowered:
                candidates.append(token)

        if re.search(r"\bUN\b", repaired):
            candidates.append("UN")

        if "wmt" in lowered and not any(candidate.lower().startswith("wmt ") for candidate in candidates):
            candidates.append("WMT")

        deduped: list[str] = []
        seen: set[str] = set()
        specific_wmt_years = {
            match.group(1)
            for candidate in candidates
            if (match := re.match(r"^WMT (\d{4}) English-to-", candidate, flags=re.IGNORECASE))
        }
        for item in candidates:
            if not self._is_valid_dataset_name(item):
                continue
            generic_match = re.match(r"^WMT (\d{4})$", item, flags=re.IGNORECASE)
            if generic_match and generic_match.group(1) in specific_wmt_years:
                continue
            key = item.lower()
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
            if len(deduped) >= 3:
                break

        return deduped

    def _coerce_from_input_text(self, input_text: str) -> dict[str, Any] | None:
        abstract = self._extract_tag_block(input_text, "ABSTRACT")
        paper_text = self._extract_tag_block(input_text, "PAPER_TEXT")

        source_text = "\n".join([part for part in [abstract, paper_text] if part])
        if not source_text:
            return None

        abstract_sentences = self._split_sentences(abstract)
        paper_sentences = self._split_sentences(paper_text)
        all_sentences = abstract_sentences + paper_sentences
        if not all_sentences:
            return None

        problem_value = self._pick_sentence_by_keywords(
            all_sentences,
            ["problem", "task", "challenge", "goal", "aim"],
        ) or all_sentences[0]

        method_value = self._pick_method_sentence(all_sentences)
        if method_value is None and len(all_sentences) > 1:
            method_value = self._pick_sentence_by_keywords(
                all_sentences,
                ["method", "model", "approach", "framework", "architecture"],
            )

        contribution_candidates = self._pick_contribution_sentences(all_sentences, max_items=8)

        limitation_keywords = [
            "limitation",
            "limitations",
            "future work",
            "future research",
            "further research",
            "interesting direction",
            "constraint",
            "assumption",
            "weakness",
            "weaknesses",
            "shortcoming",
            "shortcomings",
            "trade-off",
            "sensitive to",
            "depends on",
            "dependency",
            "fails on",
            "struggles with",
            "cannot",
            "does not",
            "expensive",
            "costly",
            "memory",
            "compute",
            "latency",
            "scalability",
            "should not be",
            "not be the only",
            "only metric",
            "only measure",
        ]

        contrast_markers = ["however", "but", "yet", "although", "nevertheless"]

        limitation_candidates: list[str] = []
        for sentence in all_sentences:
            lowered = sentence.lower()
            has_limit_keyword = any(k in lowered for k in limitation_keywords)
            has_contrast_signal = any(k in lowered for k in contrast_markers)
            has_constraint_signal = any(
                k in lowered
                for k in [
                    "require",
                    "requires",
                    "resource",
                    "data",
                    "domain",
                    "robust",
                    "generalize",
                    "noisy",
                ]
            )

            if (
                has_limit_keyword
                or (has_contrast_signal and has_constraint_signal)
            ) and self._is_valid_limitation_item({"value": sentence, "evidence": []}):
                limitation_candidates.append(sentence)
            if len(limitation_candidates) >= 2:
                break

        paper_type = self._detect_paper_type(source_text)
        if paper_type == "survey":
            datasets = []
            metrics = []
            benchmarks = []
        else:
            datasets = self._extract_datasets_from_text(source_text)
            metrics = self._extract_metrics_from_text(source_text)
            benchmarks = self._extract_benchmarks_from_text(source_text)

        coerced = {
            "problem": {
                "value": problem_value,
                "evidence": [],
            },
            "method": {
                "value": method_value,
                "evidence": [],
            },
            "contributions": [
                {
                    "value": item,
                    "evidence": [],
                }
                for item in contribution_candidates
            ],
            "limitations": [
                {
                    "value": item,
                    "evidence": [],
                }
                for item in limitation_candidates
            ],
            "evaluation_setup": {
                "value": {
                    "datasets": datasets,
                    "metrics": metrics,
                    "benchmarks": benchmarks,
                },
                "evidence": [],
            },
        }

        if not self._has_meaningful_expected_payload(coerced):
            return None

        return coerced

    def _enrich_missing_fields_from_input_text(
        self,
        normalized: dict[str, Any],
        input_text: str,
        pages: list[dict],
    ) -> dict[str, Any]:
        if not isinstance(input_text, str) or not input_text.strip():
            return normalized

        fallback = self._coerce_from_input_text(input_text)
        if not isinstance(fallback, dict):
            return normalized

        filled_keys: list[str] = []

        problem_field = normalized.get("problem")
        fallback_problem = self._normalize_scalar_field(fallback.get("problem"))
        if (
            isinstance(problem_field, dict)
            and not problem_field.get("value")
            and fallback_problem.get("value")
        ):
            normalized["problem"] = fallback_problem
            filled_keys.append("problem")

        method_field = normalized.get("method")
        fallback_method = self._normalize_scalar_field(fallback.get("method"))
        if (
            isinstance(method_field, dict)
            and not method_field.get("value")
            and fallback_method.get("value")
        ):
            normalized["method"] = fallback_method
            filled_keys.append("method")

        contributions = normalized.get("contributions")
        if not isinstance(contributions, list):
            contributions = []
        if len(contributions) == 0:
            fallback_contributions = self._normalize_contributions_field(fallback.get("contributions"), is_fallback=True)
            if fallback_contributions:
                normalized["contributions"] = fallback_contributions
                filled_keys.append("contributions")

        limitations = normalized.get("limitations")
        if not isinstance(limitations, list):
            limitations = []
        if len(limitations) == 0:
            fallback_limitations = self._normalize_limitations_field(fallback.get("limitations"), is_fallback=True)
            if fallback_limitations:
                normalized["limitations"] = fallback_limitations
                filled_keys.append("limitations")

        evaluation_setup = normalized.get("evaluation_setup")
        fallback_eval = self._normalize_evaluation_setup(fallback.get("evaluation_setup"), pages, input_text)
        if (
            isinstance(evaluation_setup, dict)
            and isinstance(fallback_eval, dict)
            and isinstance(evaluation_setup.get("value"), dict)
        ):
            current_value = evaluation_setup.get("value") or {}
            fallback_value = fallback_eval.get("value") or {}

            has_current_eval = bool(
                (current_value.get("datasets") or [])
                or (current_value.get("metrics") or [])
                or (current_value.get("benchmarks") or [])
            )
            has_fallback_eval = bool(
                (fallback_value.get("datasets") or [])
                or (fallback_value.get("metrics") or [])
                or (fallback_value.get("benchmarks") or [])
            )

            if not has_current_eval and has_fallback_eval:
                normalized["evaluation_setup"] = fallback_eval
                filled_keys.append("evaluation_setup")

        if filled_keys:
            logger.info(
                "[LLM NORMALIZE] Enriched missing fields from input_text: %s",
                ",".join(filled_keys),
            )

        return normalized

    @staticmethod
    def _override_provider_as_regex(provider_result: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of provider_result with provider set to
        ``regex_parsing`` so the DB record correctly reflects that the
        extraction data came from deterministic regex/heuristic parsing,
        not from the LLM."""
        overridden = dict(provider_result)
        overridden["provider"] = "regex_parsing"
        overridden["model"] = REGEX_FALLBACK_MODEL
        return overridden

    @staticmethod
    def _tag_provider_schema_coercion(provider_result: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of provider_result with '+schema_coercion'
        appended to the provider name so the DB record reflects that the
        LLM did produce output but it was locally reshaped to the expected
        schema."""
        overridden = dict(provider_result)
        original = overridden.get("provider") or "unknown"
        if not original.endswith("+schema_coercion"):
            overridden["provider"] = f"{original}+schema_coercion"
        return overridden

    def _extract_with_schema_retry_once(
        self,
        prompt: str,
        fallback_prompt: str | None,
        input_text: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            provider_result = self.provider.extract_metadata(
                prompt,
                fallback_prompt=fallback_prompt,
            )
        except Exception as e:
            logger.exception(
                "[LLM SERVICE] Provider call failed on primary extraction. error=%s",
                str(e),
            )

            degraded_provider_result = {
                "provider": "regex_parsing",
                "model": REGEX_FALLBACK_MODEL,
                "raw_text": None,
                "usage": {},
            }

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SERVICE] Primary provider call failed; using deterministic fallback from input text.",
                )
                return degraded_provider_result, coerced_from_input

            logger.warning(
                "[LLM SERVICE] Primary provider call failed and no deterministic fallback available; using empty payload.",
            )
            return degraded_provider_result, {}

        raw_result = provider_result.get("result_json")

        if raw_result is None:
            raw_text = provider_result.get("raw_text")
            logger.error(
                "[LLM SERVICE] Invalid JSON from provider. raw_text=%s",
                raw_text[:2000] if raw_text else None,
            )
            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SERVICE] Invalid JSON from provider; using deterministic fallback from input text.",
                )
                return self._override_provider_as_regex(provider_result), coerced_from_input

            logger.warning(
                "[LLM SERVICE] Invalid JSON from provider and no deterministic fallback available; using empty payload.",
            )
            return provider_result, {}

        if self._has_expected_extraction_schema(raw_result):
            return provider_result, raw_result

        logger.warning(
            "[LLM SCHEMA] Unexpected schema from provider=%s model=%s keys=%s. Retrying once with schema-repair prompt.",
            provider_result.get("provider"),
            provider_result.get("model"),
            self._schema_keys_for_log(raw_result),
        )

        repair_prompt_gemini = self.prompt_builder.build_schema_repair_prompt_gemini(
            raw_result,
            input_text=input_text,
        )
        repair_prompt_gemma = self.prompt_builder.build_schema_repair_prompt_gemma(
            raw_result,
            input_text=input_text,
        )
        try:
            repaired_provider_result = self.provider.extract_metadata(
                repair_prompt_gemini,
                fallback_prompt=repair_prompt_gemma,
            )
        except Exception as e:
            logger.exception(
                "[LLM SCHEMA] Schema-repair provider call failed. error=%s",
                str(e),
            )

            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair provider failed; using local schema coercion from first response.",
                )
                return self._tag_provider_schema_coercion(provider_result), coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair provider failed; using deterministic fallback from input text.",
                )
                return self._override_provider_as_regex(provider_result), coerced_from_input

            logger.warning(
                "[LLM SCHEMA] Schema-repair provider failed and no fallback available; using empty payload.",
            )
            return provider_result, {}

        repaired_raw_result = repaired_provider_result.get("result_json")

        if repaired_raw_result is None:
            raw_text = repaired_provider_result.get("raw_text")
            logger.error(
                "[LLM SCHEMA] Schema-repair retry returned invalid JSON. raw_text=%s",
                raw_text[:2000] if raw_text else None,
            )
            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry JSON invalid; using local schema coercion from first response.",
                )
                return self._tag_provider_schema_coercion(provider_result), coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry JSON invalid; using deterministic fallback from input text.",
                )
                return self._override_provider_as_regex(repaired_provider_result), coerced_from_input

            logger.warning(
                "[LLM SCHEMA] Schema-repair retry JSON invalid and no fallback available; using empty payload.",
            )
            return repaired_provider_result, {}

        if not self._has_expected_extraction_schema(repaired_raw_result):
            coerced = self._coerce_unexpected_schema_to_expected(repaired_raw_result)
            if coerced is not None:
                logger.warning(
                    "[LLM SCHEMA] Schema-repair retry still non-standard; using local schema coercion.",
                )
                return self._tag_provider_schema_coercion(repaired_provider_result), coerced

            coerced_initial = self._coerce_unexpected_schema_to_expected(raw_result)
            if coerced_initial is not None:
                logger.warning(
                    "[LLM SCHEMA] Retry non-standard; using local schema coercion from first response.",
                )
                return self._tag_provider_schema_coercion(provider_result), coerced_initial

            coerced_from_input = self._coerce_from_input_text(input_text)
            if coerced_from_input is not None:
                logger.warning(
                    "[LLM SCHEMA] Retry non-standard; using deterministic fallback from input text.",
                )
                return self._override_provider_as_regex(repaired_provider_result), coerced_from_input

            logger.error(
                "[LLM SCHEMA] Schema-repair retry failed. provider=%s model=%s keys=%s",
                repaired_provider_result.get("provider"),
                repaired_provider_result.get("model"),
                self._schema_keys_for_log(repaired_raw_result),
            )
            logger.warning(
                "[LLM SCHEMA] Retry exhausted with non-standard schema; using empty payload to avoid hard failure.",
            )
            return repaired_provider_result, {}

        logger.info(
            "[LLM SCHEMA] Schema-repair retry succeeded. provider=%s model=%s",
            repaired_provider_result.get("provider"),
            repaired_provider_result.get("model"),
        )

        return repaired_provider_result, repaired_raw_result

    def _detect_paper_type(self, text: str) -> str:
        t = text.lower()

        # Only high-confidence software/system papers get system-specific fixes.
        system_patterns = [
            (
                r"\bwe\s+(?:introduce|present|propose|develop|describe)\s+"
                r"(?:a|an|the|our)?\s*"
                r"(?:[a-z0-9_-]+\s+){0,4}"
                r"(?:metadata\s+format|data\s+format|framework|toolkit|tool|platform|"
                r"library|software|system)\b"
            ),
            (
                r"\bthis\s+(?:paper|work|study)\s+"
                r"(?:introduces|presents|proposes|describes)\s+"
                r"(?:a|an|the)?\s*"
                r"(?:[a-z0-9_-]+\s+){0,4}"
                r"(?:metadata\s+format|data\s+format|framework|toolkit|tool|platform|"
                r"library|software|system)\b"
            ),
            r"\bmetadata\s+format\b",
        ]
        if any(re.search(pattern, t) for pattern in system_patterns):
            return "system"

        if any(k in t for k in [
            "survey",
            "review of",
            "we review",
        ]):
            return "survey"

        if any(k in t for k in [
            "experimental results",
            "accuracy",
            "f1 score",
            "outperforms",
            "benchmark",
        ]):
            return "benchmark"

        return "other"
    def _infer_evaluation_evidence_from_pages(
        self,
        pages: list[dict],
    ) -> list[dict[str, Any]]:
        keywords = [
            "evaluation",
            "user study",
            "annotator",
            "annotators",
            "bleu",
            "likert",
            "completeness",
            "readability",
            "understandability",
            "consistency",
        ]

        best_candidate = None

        for page in pages:
            page_num = page.get("page")
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue

            lines = [line.strip() for line in page_text.splitlines() if line.strip()]

            for line in lines:
                lower_line = line.lower()

                if not any(k in lower_line for k in keywords):
                    continue

                # ❌ reject nếu quá nhiều số
                if sum(c.isdigit() for c in line) > len(line) * 0.3:
                    continue

                # ❌ reject nếu bị dính chữ (no spaces)
                if len(line.split()) < 5:
                    continue

                # ưu tiên câu dài hơn (nhiều thông tin hơn)
                if best_candidate is None or len(line) > len(best_candidate["snippet"]):
                    best_candidate = {
                        "snippet": re.sub(r"\s+", " ", line)[:180],
                        "page": self._coerce_page_number(page_num),
                        "section": None,
                    }

        if best_candidate:
            return [best_candidate]

        return []

    def _apply_semantic_correction(
        self,
        raw_result: dict,
        full_text: str,
    ) -> dict:
        if not raw_result:
            return raw_result

        paper_type = self._detect_paper_type(full_text)

        # Croissant-like system papers may omit human-evaluation metrics.
        if paper_type == "system":
            eval_setup = raw_result.get("evaluation_setup") or {}
            value = eval_setup.get("value") or {}

            metrics = [
                metric
                for metric in value.get("metrics", [])
                if isinstance(metric, str) and metric.strip()
            ]

            t = full_text.lower()

            if "likert" in t:
                metrics.append("Likert scale")

            if "bleu" in t:
                metrics.append("BLEU score")

            if "readability" in t:
                metrics.append("readability")

            if "completeness" in t:
                metrics.append("completeness")

            if "consistency" in t:
                metrics.append("consistency")

            value["metrics"] = self._dedupe_strings(metrics, max_items=5)

            eval_setup["value"] = value
            raw_result["evaluation_setup"] = eval_setup

        return raw_result

    def run_for_canonical_document(self, canonical_document_id: UUID) -> ExtractionRun:
        canonical = self._get_canonical_or_raise(canonical_document_id)

        cached_run = self.repo.get_latest_completed_by_canonical_document_id(
            canonical.id,
            prompt_version=PROMPT_VERSION,
        )
        if cached_run:
            logger.info("[LLM SERVICE] Cache hit for canonical_document_id=%s", canonical.id)
            setattr(cached_run, "cache_hit", True)

            return cached_run

        logger.info("[LLM SERVICE] Cache miss for canonical_document_id=%s", canonical.id)

        run = self._create_running_extraction_run(canonical.id)

        try:
            full_text, pages = self._load_full_text_for_canonical(canonical)
            text_len = len((full_text or "").strip())

            logger.info(
                "[LLM SERVICE] canonical_id=%s extracted_text_len=%s",
                canonical.id,
                text_len,
            )

            if text_len < 500:
                logger.warning(
                    "[LLM SERVICE] Skipping LLM due to insufficient text canonical_id=%s",
                    canonical.id,
                )
                raise ValueError("Insufficient text for LLM extraction")

            input_text = self.input_builder.build(
                canonical,
                parsed_text=None,
                full_text=full_text,
                pages=pages,
            )
            prompt_gemini = self.prompt_builder.build_extraction_prompt_gemini(input_text)
            prompt_gemma = self.prompt_builder.build_extraction_prompt_gemma(input_text)
            provider_result, raw_result = self._extract_with_schema_retry_once(
                prompt=prompt_gemini,
                fallback_prompt=prompt_gemma,
                input_text=input_text,
            )
            raw_result = self._apply_semantic_correction(raw_result, full_text)

            result_json = self._normalize_result(
                raw_result,
                pages,
                input_text=input_text,
            )

            run.provider = provider_result.get("provider")
            run.model_name = provider_result.get("model")

            run = self.repo.mark_completed(
                run,
                result_json=result_json,
                problem_statement=result_json.get("problem"),
                main_method=result_json.get("method"),
                contributions=result_json.get("contributions"),
                limitations=result_json.get("limitations"),
                evaluation_setup=result_json.get("evaluation_setup"),
                raw_llm_response=provider_result.get("raw_text"),
                token_input=(provider_result.get("usage") or {}).get("prompt_tokens"),
                token_output=(provider_result.get("usage") or {}).get("completion_tokens"),
            )

            self.repo.set_latest_for_canonical_document(canonical, run)
            setattr(run, "cache_hit", False)

            return run

        except Exception as e:
            self.repo.mark_failed(
                run,
                error_message=str(e),
                raw_llm_response=None,
            )

            canonical.extraction_cache_status = "failed"
            self.db.add(canonical)
            self.db.commit()
            raise

    def _get_canonical_or_raise(self, canonical_document_id: UUID) -> CanonicalDocument:
        canonical = (
            self.db.query(CanonicalDocument)
            .filter(CanonicalDocument.id == canonical_document_id)
            .first()
        )
        if not canonical:
            raise ValueError(f"CanonicalDocument not found: {canonical_document_id}")
        return canonical

    def _create_running_extraction_run(self, canonical_document_id: UUID) -> ExtractionRun:
        return self.repo.create(
            ExtractionRun(
                canonical_document_id=canonical_document_id,
                provider="pending",
                model_name="pending",
                prompt_version=PROMPT_VERSION,
                status="running",
                is_from_cache=False,
            )
        )

    def _load_full_text_for_canonical(
        self,
        canonical: CanonicalDocument,
    ) -> tuple[Optional[str], list[dict]]:

        if not canonical.papers:
            return None, []

        storage = StorageService()

        # 🔥 1. ưu tiên docling markdown
        for paper in canonical.papers:
            md_path = getattr(paper, "docling_markdown_storage_path", None)
            if not md_path:
                continue

            try:
                md_bytes = storage.download_by_storage_path(md_path)
                markdown = md_bytes.decode("utf-8")

                text_len = len((markdown or "").strip())

                logger.info(
                    "[LLM SERVICE] Loaded DOCILING markdown for canonical=%s paper_id=%s text_len=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    text_len,
                )

                if text_len > 0:
                    # ⚠️ docling chưa có page mapping → để empty hoặc simple mapping
                    docling_pages_path = getattr(
                        paper,
                        "docling_page_text_json_storage_path",
                        None,
                    )
                    pages_path = docling_pages_path or getattr(
                        paper,
                        "page_text_json_storage_path",
                        None,
                    )
                    pages_source = "docling_pages" if docling_pages_path else "pages.json"

                    pages = []

                    if pages_path:
                        try:
                            pages_bytes = storage.download_by_storage_path(pages_path)
                            pages = json.loads(pages_bytes.decode("utf-8"))

                            logger.info(
                                "[LLM SERVICE] Loaded %s for canonical=%s paper_id=%s pages=%s",
                                pages_source,
                                canonical.id,
                                getattr(paper, "id", None),
                                len(pages),
                            )
                        except Exception as e:
                            logger.warning(
                                "[LLM SERVICE] Failed to load %s canonical=%s paper_id=%s error=%s",
                                pages_source,
                                canonical.id,
                                getattr(paper, "id", None),
                                str(e),
                            )

                    return markdown, pages

            except Exception as e:
                logger.warning(
                    "[LLM SERVICE] Failed to load docling markdown for canonical=%s paper_id=%s error=%s",
                    canonical.id,
                    getattr(paper, "id", None),
                    str(e),
                )

        # 🔽 2. fallback pdfplumber (giữ lại)
        logger.warning(
            "[LLM SERVICE] Falling back to pdfplumber for canonical=%s",
            canonical.id,
        )

        for paper in canonical.papers:
            if not paper.storage_path:
                continue

            tmp_path = None

            try:
                pdf_bytes = storage.download_by_storage_path(paper.storage_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(pdf_bytes)
                    tmp_path = tmp.name

                full_text, _, pages = extract_pdf_text_for_llm(tmp_path)

                text_len = len((full_text or "").strip())

                if text_len > 0:
                    return full_text, pages

            except Exception as e:
                logger.warning(
                    "[LLM SERVICE] Failed fallback pdfplumber canonical=%s error=%s",
                    canonical.id,
                    str(e),
                )

            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        return None, []

    def _is_placeholder_text(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False

        normalized = re.sub(r"\s+", " ", value).strip().lower()
        if not normalized:
            return False

        placeholders = {
            "string",
            "string | null",
            "integer",
            "integer | null",
            "number",
            "number | null",
            "boolean",
            "boolean | null",
            "null",
            "none",
            "n/a",
            "na",
            "unknown",
            "placeholder",
            "tbd",
            "to be determined",
        }

        if normalized in placeholders:
            return True

        if normalized.startswith("<") and normalized.endswith(">"):
            return True

        return False

    @staticmethod
    def _coerce_page_number(value: Any) -> int | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value if value > 0 else None

        if isinstance(value, str):
            normalized = value.strip().lower()
            match = re.fullmatch(r"(?:p(?:age)?\.?[:\s]*)?(\d+)", normalized)
            if match:
                page_number = int(match.group(1))
                return page_number if page_number > 0 else None

        return None

    @staticmethod
    def _normalize_text_for_page_match(value: str) -> str:
        if not isinstance(value, str):
            return ""

        text = (value or "").lower()
        text = re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "", text)
        text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _significant_match_tokens(normalized_text: str) -> list[str]:
        return [
            token
            for token in normalized_text.split()
            if len(token) > 2 and token not in PAGE_MATCH_STOPWORDS
        ]

    @staticmethod
    def _contains_token_window(page_text: str, snippet_tokens: list[str]) -> bool:
        if len(snippet_tokens) < 4:
            return False

        for window_size in (8, 6, 4):
            if len(snippet_tokens) < window_size:
                continue

            for index in range(0, len(snippet_tokens) - window_size + 1):
                phrase = " ".join(snippet_tokens[index:index + window_size])
                if phrase in page_text:
                    return True

        return False

    def _normalize_evidence(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue

            snippet = item.get("snippet")
            if not isinstance(snippet, str) or not snippet.strip():
                continue

            snippet = snippet.strip()
            if self._is_placeholder_text(snippet):
                continue

            # loại table numeric
            if sum(c.isdigit() for c in snippet) > len(snippet) * 0.4:
                continue

            # loại multi-line numeric dump
            if "\n" in snippet and any(c.isdigit() for c in snippet):
                continue

            # repair spacing mạnh hơn
            snippet = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', snippet)
            snippet = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', snippet)
            snippet = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', snippet)
            snippet = re.sub(r'(?<=[,.;:])(?=[A-Za-z])', ' ', snippet)

            # xử lý một số pattern dính phổ biến
            snippet = re.sub(r'(?<=[a-z])(?=[A-Z][a-z])', ' ', snippet)
            # fix missing spaces heuristic
            # snippet = re.sub(r'([a-z])([a-z]{2,})', r'\1 \2', snippet)
            snippet = re.sub(r'\s+', ' ', snippet).strip()

            if not snippet:
                continue

            if len(snippet) > 180:
                cut = snippet[:180]
                last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
                if last_stop > 80:
                    snippet = cut[:last_stop].strip()
                else:
                    snippet = cut.strip()

            normalized.append(
                {
                    "snippet": snippet,
                    "page": self._coerce_page_number(item.get("page")),
                    "section": item.get("section") if isinstance(item.get("section"), str) else None,
                }
            )

        return normalized

    def _build_fallback_evidence_from_text(
        self,
        text: str,
        pages: list[dict],
    ) -> list[dict[str, Any]]:
        if not isinstance(text, str):
            return []

        snippet = re.sub(r"\s+", " ", text).strip()
        if not snippet or self._is_placeholder_text(snippet):
            return []

        if len(snippet) > 180:
            cut = snippet[:180]
            last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","), cut.rfind(" "))
            if last_stop > 80:
                snippet = cut[:last_stop].strip()
            else:
                snippet = cut.strip()

        if not snippet:
            return []

        return [
            {
                "snippet": snippet,
                "page": self._match_snippet_to_page(snippet, pages),
                "section": None,
            }
        ]

    def _normalize_scalar_field(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {"value": None, "evidence": []}

        if isinstance(raw, str):
            value = raw.strip() or None
            if value and self._is_placeholder_text(value):
                value = None
            return {"value": value, "evidence": []}

        if not isinstance(raw, dict):
            return {"value": None, "evidence": []}

        value = raw.get("value")
        if not isinstance(value, str):
            value = None
        else:
            value = value.strip() or None
            if value and self._is_placeholder_text(value):
                value = None

        evidence = self._normalize_evidence(raw.get("evidence"))

        return {
            "value": value,
            "evidence": evidence,
        }

    def _normalize_list_field(
        self,
        raw: Any,
        max_items: int = 3,
    ) -> list[dict[str, Any]]:
        if raw is None:
            return []

        normalized_items: list[dict[str, Any]] = []

        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str):
                    value = x.strip()
                    if not value or self._is_placeholder_text(value):
                        continue

                    normalized_items.append(
                        {
                            "value": value,
                            "evidence": [],
                        }
                    )
                    continue

                if not isinstance(x, dict):
                    continue

                value = x.get("value")
                if not isinstance(value, str) or not value.strip():
                    continue

                if self._is_placeholder_text(value):
                    continue

                evidence = self._normalize_evidence(x.get("evidence"))
                normalized_items.append({
                    "value": value.strip(),
                    "evidence": evidence,
                })

            return self._dedupe_list_items(normalized_items, max_items=max_items)

        if not isinstance(raw, dict):
            return []

        # backward-compatible old format:
        # {"items": ["a", "b"], "evidence": [...]}
        raw_items = raw.get("items")
        if raw_items is None:
            raw_items = raw.get("value")

        if not isinstance(raw_items, list):
            return []

        evidence = self._normalize_evidence(raw.get("evidence"))
        for x in raw_items:
            if not isinstance(x, str) or not x.strip():
                continue

            if self._is_placeholder_text(x):
                continue

            normalized_items.append({
                "value": x.strip(),
                "evidence": evidence,
            })

        return self._dedupe_list_items(normalized_items, max_items=max_items)

    def _normalize_evaluation_setup(
        self,
        raw: Any,
        pages: list[dict],
        source_text: str = "",
    ) -> dict[str, Any]:
        empty_value = {
            "datasets": [],
            "metrics": [],
            "benchmarks": [],
        }

        if not isinstance(raw, dict):
            raw = {}

        value = raw.get("value")
        if not isinstance(value, dict):
            value = {}

        raw_datasets = [
            re.sub(r"\s+", " ", x).strip()
            for x in value.get("datasets", [])
            if isinstance(x, str)
            and x.strip()
            and not self._is_placeholder_text(x)
            and self._is_valid_dataset_name(x)
        ]
        paper_type = self._detect_paper_type(source_text)
        if paper_type == "survey":
            extracted_datasets = []
            extracted_metrics = []
            extracted_benchmarks = []
        else:
            extracted_datasets = self._extract_datasets_from_text(source_text)
            extracted_metrics = self._extract_metrics_from_text(source_text)
            extracted_benchmarks = self._extract_benchmarks_from_text(source_text)

        datasets = self._dedupe_strings(
            raw_datasets + extracted_datasets,
            max_items=3,
        )

        raw_metrics: list[str] = []
        for x in value.get("metrics", []):
            metric = self._normalize_metric_name(x) if isinstance(x, str) else None
            if metric:
                raw_metrics.append(metric)
        metrics = self._dedupe_strings(
            raw_metrics + extracted_metrics,
            max_items=5,
        )

        raw_benchmarks: list[str] = []
        for x in value.get("benchmarks", []):
            normalized = self._normalize_benchmark_name(x)
            if normalized and not self._is_placeholder_text(normalized):
                raw_benchmarks.append(normalized)
        benchmarks = self._dedupe_strings(
            raw_benchmarks + extracted_benchmarks,
            max_items=3,
        )

        evidence = self._normalize_evidence(raw.get("evidence"))

        has_content = bool(datasets or metrics or benchmarks)

        # 🔥 fallback nếu evidence bị drop
        if has_content and not evidence:
            fallback = self._infer_evaluation_evidence_from_pages(pages)
            if fallback:
                logger.info("[LLM NORMALIZE] Using fallback evidence for evaluation_setup")
                evidence = fallback

        # ❗ nếu vẫn không có evidence → drop để pass schema
        if has_content and not evidence:
            logger.warning("[LLM NORMALIZE] Dropping evaluation_setup due to missing evidence")
            return {"value": empty_value, "evidence": []}

        return {
            "value": {
                "datasets": datasets,
                "metrics": metrics,
                "benchmarks": benchmarks,
            },
            "evidence": evidence,
        }

    def _ensure_evidence_from_values(
        self,
        normalized: dict[str, Any],
        pages: list[dict],
    ) -> dict[str, Any]:
        for scalar_key in ["problem", "method"]:
            field = normalized.get(scalar_key) or {}
            value = field.get("value") if isinstance(field, dict) else None
            evidence = field.get("evidence") if isinstance(field, dict) else []
            if isinstance(value, str) and value.strip() and (not isinstance(evidence, list) or len(evidence) == 0):
                field["evidence"] = self._build_fallback_evidence_from_text(value, pages)

        for list_key in ["contributions", "limitations"]:
            items = normalized.get(list_key)
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                value = item.get("value")
                evidence = item.get("evidence")
                if isinstance(value, str) and value.strip() and (not isinstance(evidence, list) or len(evidence) == 0):
                    item["evidence"] = self._build_fallback_evidence_from_text(value, pages)

        evaluation_setup = normalized.get("evaluation_setup")
        if isinstance(evaluation_setup, dict):
            evidence = evaluation_setup.get("evidence")
            value = evaluation_setup.get("value")

            if (not isinstance(evidence, list) or len(evidence) == 0) and isinstance(value, dict):
                tokens: list[str] = []
                for key in ["datasets", "metrics", "benchmarks"]:
                    arr = value.get(key)
                    if isinstance(arr, list):
                        tokens.extend([x for x in arr if isinstance(x, str) and x.strip()])

                if tokens:
                    evaluation_setup["evidence"] = self._build_fallback_evidence_from_text(
                        "; ".join(tokens),
                        pages,
                    )

        return normalized

    def _normalize_result(
        self,
        raw: dict[str, Any] | None,
        pages: list[dict],
        input_text: str = "",
    ) -> dict[str, Any]:
        raw = raw or {}

        normalized = {
            "problem": self._normalize_scalar_field(raw.get("problem")),
            "method": self._normalize_method_field(raw.get("method")),
            "contributions": self._normalize_contributions_field(raw.get("contributions"), is_fallback=False),
            "limitations": self._normalize_limitations_field(raw.get("limitations"), is_fallback=False),
            "evaluation_setup": self._normalize_evaluation_setup(raw.get("evaluation_setup"), pages, input_text),
        }
        normalized = self._enrich_missing_fields_from_input_text(normalized, input_text, pages)
        normalized = self._ensure_evidence_from_values(normalized, pages)
        normalized["problem"] = self._fill_missing_pages(normalized["problem"], pages)
        normalized["method"] = self._fill_missing_pages(normalized["method"], pages)
        normalized["contributions"] = self._fill_missing_pages(normalized["contributions"], pages)
        normalized["limitations"] = self._fill_missing_pages(normalized["limitations"], pages)
        normalized["evaluation_setup"] = self._fill_missing_pages(normalized["evaluation_setup"], pages)
        normalized["limitations"] = self._filter_limitations_by_source_context(
            normalized["limitations"],
            input_text,
        )
        return ExtractionResultSchema(**normalized).model_dump()
    
    def _match_snippet_to_page(
        self,
        snippet: str,
        pages: list[dict],
    ) -> int | None:
        page, _section = self._match_snippet_to_page_and_section(snippet, pages)
        return page

    def _match_snippet_to_page_and_section(
        self,
        snippet: str,
        pages: list[dict],
        page_filter: int | None = None,
    ) -> tuple[int | None, str | None]:
        snippet = (snippet or "").strip()
        if not snippet:
            return None, None

        normalized_snippet = self._normalize_text_for_page_match(snippet)
        if not normalized_snippet:
            return None, None

        snippet_words = normalized_snippet.split()
        snippet_tokens = self._significant_match_tokens(normalized_snippet)
        best_fuzzy_match: tuple[float, int, str | None] | None = None

        def score_text(candidate_text: str) -> float:
            if not candidate_text:
                return 0.0

            if snippet in candidate_text:
                return 1.0

            normalized_candidate = self._normalize_text_for_page_match(candidate_text)
            if not normalized_candidate:
                return 0.0

            if normalized_snippet in normalized_candidate:
                return 1.0

            if self._contains_token_window(normalized_candidate, snippet_words):
                return 0.92

            if len(snippet_tokens) < 4:
                return 0.0

            candidate_tokens = set(normalized_candidate.split())
            overlap = sum(1 for token in snippet_tokens if token in candidate_tokens)
            return overlap / len(snippet_tokens)

        for page in pages:
            page_num = self._coerce_page_number(page.get("page"))
            if page_num is None:
                continue

            if page_filter is not None and page_num != page_filter:
                continue

            page_sections = page.get("sections")
            fallback_section = (
                page_sections[0]
                if isinstance(page_sections, list)
                and len(page_sections) == 1
                and isinstance(page_sections[0], str)
                else None
            )

            blocks = page.get("blocks")
            if isinstance(blocks, list):
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    block_text = (block.get("text") or "").strip()
                    block_score = score_text(block_text)
                    if block_score < 0.75:
                        continue

                    block_section = block.get("section")
                    section = block_section if isinstance(block_section, str) and block_section.strip() else fallback_section
                    if block_score >= 1.0:
                        return page_num, section
                    if best_fuzzy_match is None or block_score > best_fuzzy_match[0]:
                        best_fuzzy_match = (block_score, page_num, section)

            page_score = score_text((page.get("text") or "").strip())
            if page_score >= 1.0:
                return page_num, fallback_section
            if page_score >= 0.75 and (
                best_fuzzy_match is None or page_score > best_fuzzy_match[0]
            ):
                best_fuzzy_match = (page_score, page_num, fallback_section)

        if best_fuzzy_match:
            return best_fuzzy_match[1], best_fuzzy_match[2]
        return None, None
    
    def _fill_missing_pages(
        self,
        field_obj: Any,
        pages: list[dict],
    ) -> Any:
        if not field_obj:
            return field_obj

        if isinstance(field_obj, list):
            normalized_items: list[dict[str, Any]] = []

            for item in field_obj:
                if not isinstance(item, dict):
                    continue

                evidences = item.get("evidence") or []
                for ev in evidences:
                    if ev.get("page") is None or not ev.get("section"):
                        current_page = self._coerce_page_number(ev.get("page"))
                        matched_page, matched_section = self._match_snippet_to_page_and_section(
                            ev.get("snippet", ""),
                            pages,
                            page_filter=current_page,
                        )
                        if matched_page is None and current_page is not None:
                            matched_page, matched_section = self._match_snippet_to_page_and_section(
                                ev.get("snippet", ""),
                                pages,
                            )
                        if matched_page is not None:
                            ev["page"] = matched_page
                        if not ev.get("section") and matched_section:
                            ev["section"] = matched_section

                normalized_items.append(item)

            return normalized_items

        if isinstance(field_obj, dict):
            evidences = field_obj.get("evidence") or []

            for ev in evidences:
                if ev.get("page") is None or not ev.get("section"):
                    current_page = self._coerce_page_number(ev.get("page"))
                    matched_page, matched_section = self._match_snippet_to_page_and_section(
                        ev.get("snippet", ""),
                        pages,
                        page_filter=current_page,
                    )
                    if matched_page is None and current_page is not None:
                        matched_page, matched_section = self._match_snippet_to_page_and_section(
                            ev.get("snippet", ""),
                            pages,
                        )
                    if matched_page is not None:
                        ev["page"] = matched_page
                    if not ev.get("section") and matched_section:
                        ev["section"] = matched_section

            return field_obj

        return field_obj
