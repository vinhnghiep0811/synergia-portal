import hashlib
import re
from typing import List, Dict, Any

from app.models.document_section import DocumentSection
from app.models.document_chunk import DocumentChunk


class DocumentStructureService:
    SECTION_TYPE_MAP = {
        "abstract": "abstract",
        "perspective summary": "abstract",
        "summary": "abstract",

        "introduction": "introduction",
        "background": "background",
        "related work": "related_work",
        "related works": "related_work",

        "method": "method",
        "methods": "method",
        "methodology": "method",
        "approach": "method",
        "approaches": "method",

        "experiment": "evaluation",
        "experiments": "evaluation",
        "experimental setup": "evaluation",
        "evaluation": "evaluation",
        "evaluation protocols": "evaluation",
        "quantitative evaluation": "evaluation",
        "human evaluation": "evaluation",
        "ablation study": "evaluation",
        "settings": "evaluation",

        "results": "results",
        "qualitative results": "results",
        "discussion": "discussion",

        "outlook": "conclusion",
        "conclusion": "conclusion",
        "conclusions": "conclusion",

        "limitations": "limitations",
        "risks and safeguards": "discussion",
        "governance of ai agents": "discussion",

        "references": "references",
        "bibliography": "references",

        "declaration of interests": "declaration",
        "acknowledgement": "other",
        "acknowledgements": "other",
        "acknowledgment": "other",
        "acknowledgments": "other",
        "appendix": "appendix",
        "supplementary information": "appendix",

        "task planning": "method",
        "model selection": "method",
        "task execution": "method",
        "response generation": "method",

        # section hệ thống / body section hay gặp
        "hugginggpt": "method",
    }

    ALLOWED_UNNUMBERED_MAIN_HEADINGS = {
        "perspective summary",
        "abstract",
        "introduction",
        "background",
        "related work",
        "related works",
        "method",
        "methods",
        "methodology",
        "approach",
        "approaches",
        "experiments",
        "experiment",
        "evaluation",
        "results",
        "discussion",
        "conclusion",
        "conclusions",
        "limitations",
        "limitation",
        "future work",
        "references",
        "bibliography",
        "acknowledgement",
        "acknowledgements",
        "acknowledgment",
        "acknowledgments",
        "appendix",
        "supplementary information",
        "supplementary material",
    }

    KNOWN_HEADING_KEYWORDS = {
        "abstract",
        "introduction",
        "background",
        "related work",
        "related works",
        "method",
        "methods",
        "methodology",
        "approach",
        "approaches",
        "experiment",
        "experiments",
        "evaluation",
        "results",
        "discussion",
        "conclusion",
        "conclusions",
        "limitations",
        "limitation",
        "future work",
        "references",
        "bibliography",
        "appendix",
        "task planning",
        "model selection",
        "task execution",
        "response generation",
        "perspective summary",
    }

    FRONT_MATTER_HEADINGS = {
        "author",
        "authors",
        "affiliation",
        "affiliations",
        "contact",
        "contacts",
        "correspondence",
        "author information",
        "author details",
    }

    AFFILIATION_KEYWORDS = (
        "university",
        "college",
        "school",
        "department",
        "institute",
        "faculty",
        "laboratory",
        "lab",
        "hospital",
        "clinic",
        "research center",
        "research centre",
        "research institute",
        "corresponding author",
        "equal contribution",
    )

    def _is_retrievable_section(self, section: DocumentSection) -> bool:
        if not section:
            return True

        section_type = (section.section_type or "").strip().lower()
        section_name = (section.section_name or "").strip().lower()
        heading_level = getattr(section, "heading_level", None)

        # bỏ Document/front matter
        if heading_level == 0 or section_name == "document":
            return False

        # references thường không dùng cho semantic retrieval thường
        if section_type in {"references", "appendix"}:
            return False

        return True

    def _should_skip_section_content(self, section: DocumentSection, text: str) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return True

        section_name = (section.section_name or "").strip().lower()
        heading_level = getattr(section, "heading_level", None)

        # bỏ front matter
        if heading_level == 0 and not text:
            return True

        return False

    def _extract_heading_info(self, line: str) -> Dict[str, Any]:
        markdown_heading_match = re.match(r"^(#+)\s*(.*)$", line.strip())
        markdown_heading_level = None
        if markdown_heading_match:
            markdown_heading_level = len(markdown_heading_match.group(1))
            line = markdown_heading_match.group(2).strip()

        line = re.sub(r"\s+", " ", line).strip()

        m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", line)
        if m:
            heading_number = m.group(1).strip()
            section_name = m.group(2).strip()
            heading_level = markdown_heading_level or (heading_number.count(".") + 1)
            return {
                "heading_number": heading_number,
                "heading_level": heading_level,
                "section_name": section_name[:500],
            }

        return {
            "heading_number": None,
            "heading_level": markdown_heading_level or 1,
            "section_name": line[:500],
        }

    def parse_markdown_to_sections(
        self,
        canonical_document_id,
        markdown: str,
    ) -> List[DocumentSection]:
        lines = markdown.splitlines()

        sections: List[Dict[str, Any]] = []
        sections_by_key: Dict[str, Dict[str, Any]] = {}

        current_title = "Document"
        current_type = "other"
        current_heading_number = None
        current_heading_level = 0
        current_parent_key = None
        current_lines: List[str] = []
        section_index = 0

        seen_main_section = False
        # in_references = False

        # stack[level] = section_key gần nhất ở level đó
        heading_stack: Dict[int, str] = {}

        def flush_section():
            nonlocal section_index, current_lines
            nonlocal current_title, current_type, current_heading_number, current_heading_level, current_parent_key
            if not seen_main_section:
                return
            content = "\n".join(current_lines).strip()

            # chỉ bỏ nếu vừa không có content, vừa không phải heading thật
            if not content and current_title == "Document" and current_heading_level == 0:
                return

            if not seen_main_section and current_type == "other":
                return

            section_key = self._make_section_key(section_index)
            full_path = self._build_full_path(
                section_name=current_title,
                parent_key=current_parent_key,
                sections_by_key=sections_by_key,
            )

            sec = {
                "section_index": section_index,
                "section_name": current_title,
                "section_type": current_type,
                "heading_number": current_heading_number,
                "heading_level": current_heading_level,
                "section_key": section_key,
                "parent_key": current_parent_key,
                "full_path": full_path,
                "content": content,   # có thể rỗng
            }

            sections.append(sec)
            sections_by_key[section_key] = sec

            section_index += 1
            current_lines = []

        for raw_line in lines:
            line = raw_line.strip()

            if not line:
                if seen_main_section:
                    current_lines.append(raw_line)
                continue

            if self._looks_like_affiliation_line(line):
                continue

            # if in_references:
            #     current_lines.append(raw_line)
            #     continue
            is_heading = self._is_heading(line)

            if not seen_main_section and not is_heading:
                continue
            if not seen_main_section:
                if self._looks_like_affiliation_line(line):
                    continue
            if current_type == "references" and not is_heading:
                if self._is_reference_like_line(raw_line):
                    current_lines.append(raw_line)
                continue

            if is_heading:
                if not seen_main_section:
                    current_lines = []
                heading_info = self._extract_heading_info(line)
                cleaned_title = heading_info["section_name"]
                heading_number = heading_info["heading_number"]
                heading_level = heading_info["heading_level"]
                normalized_type = self._normalize_section_type(cleaned_title)

                if not seen_main_section:
                    if normalized_type == "other":
                        continue

                is_main = self._is_main_section_heading(
                    cleaned_title,
                    normalized_type,
                    heading_level,
                )

                if not seen_main_section:
                    if self._looks_like_affiliation_line(line):
                        continue
                    allowed_before_main = (
                        self._is_allowed_unnumbered_main_heading(cleaned_title)
                        or normalized_type in {"abstract"}
                    )
                    if not allowed_before_main:
                        continue

                if (
                    seen_main_section
                    and cleaned_title.strip().lower() == current_title.strip().lower()
                    and heading_level == current_heading_level
                    and heading_number == current_heading_number
                    and normalized_type == current_type
                ):
                    continue

                flush_section()

                parent_key = None
                if heading_level > 1:
                    parent_key = heading_stack.get(heading_level - 1)

                if normalized_type == "other" and parent_key and parent_key in sections_by_key:
                    parent_section = sections_by_key[parent_key]
                    parent_type = (parent_section.get("section_type") or "").strip().lower()
                    if parent_type == "appendix":
                        normalized_type = "appendix"

                current_title = cleaned_title
                current_type = normalized_type
                current_heading_number = heading_number
                current_heading_level = heading_level
                current_parent_key = parent_key

                current_key = self._make_section_key(section_index)
                heading_stack[heading_level] = current_key

                # xóa các level sâu hơn khi gặp heading mới
                deeper_levels = [lvl for lvl in heading_stack.keys() if lvl > heading_level]
                for lvl in deeper_levels:
                    del heading_stack[lvl]

                if is_main:
                    seen_main_section = True

                # if current_type == "references":
                #     in_references = True

                continue

            if not self._looks_like_affiliation_line(raw_line):
                current_lines.append(raw_line)

        flush_section()

        if not sections and markdown.strip():
            sections.append(
                {
                    "section_index": 0,
                    "section_name": "Document",
                    "section_type": "other",
                    "heading_number": None,
                    "heading_level": 0,
                    "section_key": self._make_section_key(0),
                    "parent_key": None,
                    "full_path": "Document",
                    "content": markdown.strip(),
                }
            )

        # pass 2: map parent_key -> parent_section_id sau khi SQLAlchemy object đã được tạo
        section_objects: List[DocumentSection] = []
        object_by_key: Dict[str, DocumentSection] = {}

        for sec in sections:
            obj = DocumentSection(
                canonical_document_id=canonical_document_id,
                section_index=sec["section_index"],
                section_name=sec["section_name"],
                section_type=sec["section_type"],
                heading_number=sec["heading_number"],
                heading_level=sec["heading_level"],
                parent_section_id=None,  # set ở pass 2
                full_path=sec["full_path"],
                page_from=None,
                page_to=None,
                content=sec["content"],
            )
            section_objects.append(obj)

            section_key = sec["section_key"]
            object_by_key[section_key] = obj

        for sec, obj in zip(sections, section_objects):
            parent_key = sec["parent_key"]
            if parent_key and parent_key in object_by_key:
                obj.parent_section = object_by_key[parent_key]

        return section_objects

    def build_chunks_from_sections(
        self,
        canonical_document_id,
        sections: List[DocumentSection],
        max_chars: int = 1500,
        min_chunk_chars: int = 80,
        overlap_chars: int = 200,
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        chunk_index = 0

        for section in sections:

            section_type = (section.section_type or "").strip().lower()
            if section_type in {"references", "appendix", "affiliation"}:
                continue
            
            section_text = self._clean_section_content(section.content or "")

            if self._should_skip_section_content(section, section_text):
                continue
            dynamic_max_chars = self._get_section_chunk_size(section, default=max_chars)

            parts = self._split_text(section_text, max_chars=dynamic_max_chars, overlap_chars=overlap_chars)

            for part in parts:
                normalized = self._normalize_chunk_text(part)
                if not normalized:
                    continue

                if self._should_drop_chunk(normalized, min_chunk_chars=min_chunk_chars):
                    continue

                prefix = f"{section.section_name}\n" if section.section_name else ""
                final_content = prefix + normalized
                hash_input = f"{section.full_path}\n{normalized}" if section.full_path else normalized
                content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

                is_retrievable = self._is_retrievable_section(section)

                chunks.append(
                    DocumentChunk(
                        canonical_document_id=canonical_document_id,
                        section_id=section.id if getattr(section, "id", None) else None,
                        chunk_index=chunk_index,
                        section=section.section_name,
                        section_type=section.section_type,
                        section_heading_level=section.heading_level,
                        section_full_path=section.full_path,
                        is_retrievable=is_retrievable,
                        page_from=section.page_from,
                        page_to=section.page_to,
                        content=final_content,
                        content_hash=content_hash,
                        token_count=self._estimate_token_count(final_content),
                    )
                )
                chunk_index += 1

        return chunks

    def _is_reference_like_line(self, line: str) -> bool:
        stripped = (line or "").strip()
        lower = stripped.lower()

        if not stripped:
            return True

        if self._looks_like_reference_entry(stripped):
            return True

        if "proc." in lower or "vol." in lower or "no." in lower or "pp." in lower:
            return True

        if lower.startswith("in ") and len(stripped.split()) >= 4:
            return True

        if re.search(r"\b(19|20)\d{2}\b", stripped) and len(stripped.split()) >= 3:
            return True

        return False

    def _is_heading(self, line: str) -> bool:
        if not line:
            return False

        line = line.replace("\u00a0", " ").strip()
        lower = line.lower()
        candidate_title = self._clean_heading(line)
        lower_candidate = candidate_title.lower().strip()
        if self._looks_like_affiliation_line(line): 
            return False

        if len(line) > 120:
            return False
        
        if lower_candidate in self.KNOWN_HEADING_KEYWORDS or any(kw in lower for kw in ["summary", "abstract"]):
            return True

        if self._is_noise_line(line):
            return False

        if self._looks_like_reference_entry(line):
            return False

        if line.endswith(":") and len(line.split()) <= 6:
            return False

        if self._looks_like_front_matter_heading(candidate_title):
            return False

        if line.startswith("#"):
            return True

        if re.match(r"^\d+(\.\d+)*\.?\s+[A-Za-z]", line):
            if len(line.split()) <= 14:
                if self._looks_like_affiliation_line(line):
                    return False
                return True

        if lower in self.KNOWN_HEADING_KEYWORDS:
            return True

        if self._contains_affiliation_keyword(line) or "email" in lower or "@" in line:
            return False

        if lower.startswith((
            "figure ", "fig. ", "table ", "algorithm ",
            "supplementary figure ", "extended data figure "
        )):
            return False

        words = line.split()
        if len(words) > 20:
            return False
        if len(words) < 1 or len(words) > 12:
            return False

        if self._looks_like_sentence(line):
            # Chỉ cho phép đi tiếp nếu là tiêu đề quan trọng (Summary/Abstract)
            if not any(kw in lower for kw in ["summary", "abstract"]):
                return False

        if self._looks_like_table_row(line):
            return False

        capitalized_ratio = sum(1 for w in words if w and w[0].isupper()) / max(1, len(words))
        uppercase_ratio = sum(1 for c in line if c.isupper()) / max(1, sum(1 for c in line if c.isalpha()))

        if capitalized_ratio >= 0.7:
            return True

        if uppercase_ratio >= 0.7 and len(words) <= 6:
            return True

        return False

    def _is_main_section_heading(self, title: str, section_type: str, heading_level: int | None = None) -> bool:
        normalized = title.strip().lower()

        if heading_level == 1:
            return True

        if section_type in {
            "abstract",
            "introduction",
            "background",
            "related_work",
            "method",
            "evaluation",
            "results",
            "discussion",
            "conclusion",
            "limitations",
            "references",
            "appendix",
            "declaration",
        }:
            return True

        allowed_titles = {
            "perspective summary",
            "challenges",
            "outlook",
            "evaluation protocols",
            "roadmap for building ai agents",
            "acknowledgement",
            "acknowledgements",
            "acknowledgment",
            "acknowledgments",
        }

        return normalized in allowed_titles

    def _clean_heading(self, line: str) -> str:
        return self._extract_heading_info(line)["section_name"]

    def _looks_like_front_matter_heading(self, title: str) -> bool:
        normalized = re.sub(r"\s+", " ", (title or "").strip().lower())
        if not normalized:
            return False

        if normalized in self.FRONT_MATTER_HEADINGS:
            return True

        return self._looks_like_affiliation_line(title)

    def _contains_affiliation_keyword(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not normalized:
            return False

        for keyword in self.AFFILIATION_KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", normalized):
                return True

        return False

    def _looks_like_reference_entry(self, line: str) -> bool:
        lower = line.lower()

        if re.match(r"^\[\d+\]", line):
            return True

        if re.match(r"^\d+\.\s+", line):
            return True

        if "doi:" in lower:
            return True

        if " et al." in lower:
            return True

        if "http://" in lower or "https://" in lower or "url " in lower:
            return True
        
        year_match = re.search(r"\b(19|20)\d{2}\b", line)
        if year_match and len(line.split()) > 8 and "." in line:
            return True

        return False

    def _normalize_section_type(self, title: str) -> str:
        normalized = title.replace("\u00a0", " ").strip().lower()
        normalized = re.sub(r"\s+", " ", normalized).strip()

        if any(kw in normalized for kw in ["perspective summary", "abstract", "summary"]):
            return "abstract"

        if normalized in self.SECTION_TYPE_MAP:
            return self.SECTION_TYPE_MAP[normalized]

        if "perspective summary" in normalized or "summary" in normalized:
            return "abstract"

        if normalized.startswith("abstract"):
            return "abstract"

        if normalized.startswith(("introduction", "motivation")):
            return "introduction"

        if normalized.startswith("background"):
            return "background"

        if "analysis" in normalized:
            return "discussion"

        if "discussion" in normalized and "result" in normalized:
            return "discussion"

        if "limitation" in normalized:
            return "limitations"

        if "case study" in normalized:
            return "evaluation"

        if "dataset" in normalized:
            return "evaluation"

        if "related work" in normalized:
            return "related_work"

        if normalized.startswith(("method", "methods", "methodology", "approach")):
            return "method"

        if any(token in normalized for token in [
            "experimental setup", "experiment", "evaluation", "benchmark", "dataset"
        ]):
            return "evaluation"

        if normalized.startswith(("result", "results")):
            return "results"

        if normalized.startswith("discussion"):
            return "discussion"

        if normalized.startswith(("conclusion", "conclusions", "future work")):
            return "conclusion"

        if normalized.startswith(("limitation", "limitations")):
            return "limitations"

        if normalized.startswith(("reference", "references", "bibliography")):
            return "references"

        if normalized.startswith(("acknowledgement", "acknowledgements", "acknowledgment", "acknowledgments")):
            return "other"

        if "experiment" in normalized and "result" in normalized:
            return "evaluation"

        if "implementation" in normalized:
            return "method"

        if "future work" in normalized:
            return "conclusion"

        if normalized == "appendix":
            return "appendix"

        if re.match(r"^[a-z]\s+appendix$", normalized):
            return "appendix"

        if normalized.startswith("appendix "):
            return "appendix"
        
        if any(token in normalized for token in [
            "university", "department", "institute", "hospital", "college"
        ]):
            return "affiliation"

        if re.match(r"^[a-z]\.\d+(\.\d+)*\s+", normalized):
            return "appendix"
        
        return "other"

    def _split_into_blocks(self, text: str) -> List[str]:
        lines = text.splitlines()
        blocks: List[str] = []
        current: List[str] = []
        current_kind: str | None = None

        def detect_kind(line: str) -> str:
            stripped = line.strip()
            lower = stripped.lower()

            if not stripped:
                return "blank"

            if self._is_noise_line(stripped):
                return "noise"

            if self._looks_like_table_separator(stripped):
                return "table"

            if stripped.startswith("|") or self._looks_like_table_row(stripped):
                return "table"

            if stripped.startswith("```"):
                return "code"

            if (
                stripped.startswith("{")
                or stripped.startswith("[")
                or stripped.startswith("}")
                or stripped.startswith("]")
                or self._looks_like_jsonish_line(stripped)
            ):
                return "code"

            if lower.startswith(("figure ", "fig. ", "table ", "algorithm ")):
                return "caption"

            if re.match(r"^[-*•]\s+", stripped):
                return "list"

            if re.match(r"^\d+\.\s+", stripped):
                return "list"

            return "paragraph"

        def flush():
            nonlocal current, current_kind
            block = "\n".join(current).strip()
            block = self._normalize_chunk_text(block)
            if block:
                blocks.append(block)
            current = []
            current_kind = None

        for line in lines:
            kind = detect_kind(line)

            if kind == "noise":
                continue

            if kind == "blank":
                flush()
                continue

            if current_kind is None:
                current = [line]
                current_kind = kind
                continue
            # merge caption + table
            if current_kind == "caption" and kind in {"table", "code", "paragraph"}:
                current.append(line)
                current_kind = kind if kind != "paragraph" else "caption"
                continue

            if current_kind == "paragraph" and kind == "paragraph":
                if self._should_merge_short_line(current[-1], line):
                    current[-1] = current[-1].rstrip() + " " + line.strip()
                else:
                    current.append(line)
                continue

            if kind == current_kind:
                if kind in {"table", "list"}:
                    current.append(line)
                elif kind == "paragraph" and self._should_merge_short_line(current[-1], line):
                    current[-1] = current[-1].rstrip() + " " + line.strip()
                else:
                    current.append(line)
            else:
                flush()
                current = [line]
                current_kind = kind

        flush()
        return blocks

    def _get_overlap(self, text: str, overlap_chars: int) -> str:
        sentences = re.split(r'(?<=[.!?])\s+', text)

        overlap = []
        total_len = 0

        for sent in reversed(sentences):
            if total_len + len(sent) > overlap_chars:
                break
            overlap.insert(0, sent)
            total_len += len(sent)

        return " ".join(overlap)

    def _split_text(
        self,
        text: str,
        max_chars: int = 1200,
        overlap_chars: int = 150,
    ) -> List[str]:

        text = self._normalize_chunk_text(text)
        if not text:
            return []

        blocks = self._split_into_blocks(text)
        if not blocks:
            blocks = [text]

        chunks: List[str] = []
        current = ""

        for block in blocks:
            block = self._normalize_chunk_text(block)
            if not block:
                continue

            semantic_units = self._split_into_semantic_units(block, max_chars=max_chars)
            fixed_units = []
            for unit in semantic_units:
                if len(unit) > max_chars:
                    fixed_units.extend(
                        self._hard_split_long_text(unit, max_chars, overlap_chars)
                    )
                else:
                    fixed_units.append(unit)

            semantic_units = fixed_units
            if not semantic_units:
                semantic_units = [block]

            temp = current

            for unit in semantic_units:
                unit = self._normalize_chunk_text(unit)
                if not unit:
                    continue
                if len(unit) > max_chars:
                    long_parts = self._hard_split_long_text(unit, max_chars, overlap_chars)
                    for lp in long_parts:
                        lp = self._normalize_chunk_text(lp)
                        if not lp:
                            continue

                        candidate = f"{temp}\n\n{lp}".strip() if temp else lp

                        if len(candidate) <= max_chars:
                            temp = candidate
                        else:
                            if temp:
                                previous_chunk = temp
                                chunks.append(previous_chunk)
                                temp = self._compose_with_overlap(
                                    previous_chunk=previous_chunk,
                                    next_text=lp,
                                    overlap_chars=overlap_chars,
                                    max_chars=max_chars,
                                )
                            else:
                                temp = lp
                    continue
                candidate = f"{temp}\n\n{unit}".strip() if temp else unit

                if len(candidate) <= max_chars:
                    temp = candidate
                    continue

                if temp:
                    previous_chunk = temp
                    chunks.append(previous_chunk)
                    temp = self._compose_with_overlap(
                        previous_chunk=previous_chunk,
                        next_text=unit,
                        overlap_chars=overlap_chars,
                        max_chars=max_chars,
                    )
                else:
                    temp = unit

            current = temp

        if current:
            chunks.append(current)

        return [c.strip() for c in chunks if c.strip()]

    def _hard_split_long_text(self, text: str, max_chars: int, overlap_chars: int = 200) -> List[str]:
        text = self._normalize_chunk_text(text)
        if len(text) <= max_chars:
            return [text]

        results = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                window = text[start:end]
                split_pos = max(
                    window.rfind("\n"),
                    window.rfind(". "),
                    window.rfind("; "),
                    window.rfind(", "),
                    window.rfind(" ")
                )
                if split_pos > max_chars * 0.5:
                    end = start + split_pos + 1

            piece = self._normalize_chunk_text(text[start:end])
            if piece:
                results.append(piece)
                
            start = end
            if start < len(text) and overlap_chars > 0:
                overlap_start = max(0, start - overlap_chars)
                window = text[overlap_start:start]
                split_pos = max(
                    window.find(". "),
                    window.find("; "),
                    window.find(", "),
                    window.find(" ")
                )
                if split_pos != -1:
                    start = overlap_start + split_pos + 1
                else:
                    start = overlap_start

        return results

    def _estimate_token_count(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _compose_with_overlap(
        self,
        previous_chunk: str,
        next_text: str,
        overlap_chars: int,
        max_chars: int,
    ) -> str:
        next_text = self._normalize_chunk_text(next_text)
        if not next_text:
            return ""

        if not previous_chunk or overlap_chars <= 0:
            return next_text

        overlap = self._get_overlap(previous_chunk, overlap_chars)
        if not overlap:
            return next_text

        candidate = f"{overlap} {next_text}".strip()
        candidate = re.sub(r"^[\)\]\.,\s]+", "", candidate)
        if len(candidate) <= max_chars:
            return candidate

        return next_text

    def _make_section_key(self, section_index: int) -> str:
        return f"sec:{section_index}"

    def _build_full_path(
        self,
        section_name: str,
        parent_key: str | None,
        sections_by_key: Dict[str, Dict[str, Any]],
    ) -> str:
        if not parent_key:
            return section_name

        parent = sections_by_key.get(parent_key)
        if not parent:
            return section_name

        parent_path = parent.get("full_path") or parent.get("section_name") or ""
        if not parent_path:
            return section_name

        return f"{parent_path} > {section_name}"

    def _is_allowed_unnumbered_main_heading(self, title: str) -> bool:
        normalized = title.strip().lower()
        return normalized in self.ALLOWED_UNNUMBERED_MAIN_HEADINGS

    def _looks_like_sentence(self, line: str) -> bool:
        if not line:
            return False

        if len(line.split()) >= 12:
            return True

        if any(p in line for p in [".", ";", "?", "!"]) and len(line.split()) > 6:
            return True

        lower = line.lower()
        sentence_markers = [
            " we ", " this ", " that ", " these ", " those ",
            " is ", " are ", " was ", " were ", " can ", " could ",
            " should ", " using ", " use ", " propose ", " present "
        ]
        padded = f" {lower} "
        return any(marker in padded for marker in sentence_markers)

    def _looks_like_table_row(self, line: str) -> bool:
        stripped = line.strip()

        if stripped.startswith("|") and stripped.endswith("|"):
            return True

        pipe_count = stripped.count("|")
        if pipe_count >= 2:
            return True

        if "\t" in stripped:
            cols = [c for c in stripped.split("\t") if c.strip()]
            if len(cols) >= 3:
                return True

        multi_space_cols = re.split(r"\s{3,}", stripped)
        if len([c for c in multi_space_cols if c.strip()]) >= 3:
            return True

        return False

    def _looks_like_table_separator(self, line: str) -> bool:
        stripped = line.strip()
        return bool(re.match(r"^\|?[\s:-]+\|[\s|:-]*$", stripped))

    def _looks_like_jsonish_line(self, line: str) -> bool:
        stripped = line.strip()
        if len(stripped) < 2:
            return False

        if re.search(r'"[^"]+"\s*:\s*', stripped):
            return True

        if re.search(r"'[^']+'\s*:\s*", stripped):
            return True

        if stripped.count("{") + stripped.count("}") >= 2:
            return True

        return False

    def _looks_like_affiliation_line(self, line: str) -> bool:
        stripped = (line or "").strip()
        lower = stripped.lower()

        if not stripped:
            return False

        if "@" in stripped or "orcid" in lower:
            return True

        if self._contains_affiliation_keyword(stripped):
            return True

        if re.search(r"\b(email|e-mail|address|addresses)\b", lower):
            return True

        if re.match(r"^\d+\s+", stripped) and any(
            re.search(rf"\b{re.escape(token)}\b", lower)
            for token in ["university", "department", "institute", "lab"]
        ):
            return True

        return False

    def _is_noise_line(self, line: str) -> bool:
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            return False

        if self._looks_like_table_separator(stripped):
            return True

        if re.fullmatch(r"[-_=]{3,}", stripped):
            return True

        if len(stripped) <= 2 and any(ch in stripped for ch in "{}[]|"):
            return True

        if self._looks_like_jsonish_line(stripped):
            if any(token in lower for token in [
                '"task"', '"id"', '"dep"', '"args"', '"image"', '"text"',
                "'task'", "'id'", "'dep'", "'args'", "'image'", "'text'"
            ]):
                return True

        if lower in {"prompt", "response", "input", "output"} and len(stripped.split()) == 1:
            return True

        return False

    def _should_merge_short_line(self, prev_line: str, new_line: str) -> bool:
        prev = prev_line.strip()
        new = new_line.strip()

        if not prev or not new:
            return False

        if self._looks_like_table_row(prev) or self._looks_like_table_row(new):
            return False

        if self._looks_like_jsonish_line(prev) or self._looks_like_jsonish_line(new):
            return False

        if len(new.split()) <= 8:
            return True

        if not prev.endswith((".", ":", ";", "?", "!")):
            return True

        return False

    def _clean_section_content(self, text: str) -> str:
        if not text:
            return ""
        
        cleaned_lines = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if self._looks_like_affiliation_line(line):
                continue
            if self._is_noise_line(line):
                continue
            if "|" in line:
                line = re.sub(r"\|", " ", line)

            if re.search(r"^\s*Table\s+\d+", line, flags=re.IGNORECASE):
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _normalize_chunk_text(self, text: str) -> str:
        if not text:
            return ""

        text = text.replace("\u00a0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" ?\n ?", "\n", text)
        text = re.sub(r"([a-zA-Z0-9])\n([a-z])", r"\1 \2", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\{\{.*?\}\}", "", text)
        text = re.sub(r"\|[^|\n]*\|", " ", text)
        text = re.sub(r"Table\s+\d+[:\.]?.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<!--.*?-->", "", text)
        return text.strip()

    def _should_drop_chunk(self, text: str, min_chunk_chars: int = 80) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if "|" in text and text.count("|") > 5:
            return True
        if len(stripped) < min_chunk_chars:
            if not re.search(r"[A-Za-z]{20,}", stripped):
                if not self._is_definition_sentence(stripped):
                    return True
        if len(stripped.split()) < 5 and not self._is_definition_sentence(stripped):
            return True
        alpha_count = sum(1 for c in stripped if c.isalpha())
        punct_like = sum(1 for c in stripped if c in "{}[]|:_<>/")
        if len(stripped) > 0 and punct_like / len(stripped) > 0.25 and alpha_count < 40:
            return True

        if self._looks_like_jsonish_line(stripped) and len(stripped.split()) < 30:
            return True

        return False

    def _get_section_chunk_size(self, section: DocumentSection, default: int = 3000) -> int:
        section_name = (section.section_name or "").strip().lower()
        section_type = (section.section_type or "").strip().lower()

        if section_type == "method":
            return min(default, 2200)

        if section_name in {"task planning", "model selection", "task execution", "response generation"}:
            return min(default, 1800)

        if section_type in {"abstract", "conclusion", "limitations"}:
            return min(default, 1800)

        return default
    
    def _split_into_semantic_units(self, text: str, max_chars: int = 400) -> List[str]:
        text = self._normalize_chunk_text(text)
        if not text:
            return []

        sentences = [
            sent.strip()
            for sent in re.split(r'(?<=[.!?])\s+', text)
            if sent.strip()
        ]
        if not sentences:
            return [text]

        groups = []
        current = []

        for sent in sentences:
            if len(sent) > max_chars:
                if current:
                    groups.append(" ".join(current))
                    current = []
                groups.append(sent)
                continue

            if len(" ".join(current + [sent])) <= max_chars:
                current.append(sent)
            else:
                if current:
                    groups.append(" ".join(current))
                current = [sent]

        if current:
            groups.append(" ".join(current))

        return groups
    
    def _is_definition_sentence(self, sent: str) -> bool:
        return bool(re.search(
            r"\b(is a|are a|refers to|we propose|we present)\b",
            sent.lower()
        ))
