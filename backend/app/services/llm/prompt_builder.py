import json
from typing import Any

from app.services.llm.constants import PROMPT_VERSION


class LLMPromptBuilder:
    def _get_required_schema(self) -> dict[str, Any]:
        return {
            "problem": {
                "value": "string | null",
                "evidence": [
                    {
                        "snippet": "string",
                        "page": "integer | null",
                        "section": "string | null",
                    }
                ],
            },
            "method": {
                "value": "string | null",
                "evidence": [
                    {
                        "snippet": "string",
                        "page": "integer | null",
                        "section": "string | null",
                    }
                ],
            },
            "contributions": [
                {
                    "value": "string",
                    "evidence": [
                        {
                            "snippet": "string",
                            "page": "integer | null",
                            "section": "string | null",
                        }
                    ],
                }
            ],
            "limitations": [
                {
                    "value": "string",
                    "evidence": [
                        {
                            "snippet": "string",
                            "page": "integer | null",
                            "section": "string | null",
                        }
                    ],
                }
            ],
            "evaluation_setup": {
                "value": {
                    "datasets": ["string"],
                    "metrics": ["string"],
                    "benchmarks": ["string"],
                },
                "evidence": [
                    {
                        "snippet": "string",
                        "page": "integer | null",
                        "section": "string | null",
                    }
                ],
            },
        }

    def _get_schema_repair_shape(self) -> dict[str, Any]:
        return {
            "problem": {
                "value": None,
                "evidence": [],
            },
            "method": {
                "value": None,
                "evidence": [],
            },
            "contributions": [],
            "limitations": [],
            "evaluation_setup": {
                "value": {
                    "datasets": [],
                    "metrics": [],
                    "benchmarks": [],
                },
                "evidence": [],
            },
        }

    def build_extraction_prompt_gemini(self, input_text: str) -> str:
        schema = self._get_required_schema()

        instructions = f"""
You are an academic paper metadata extraction assistant.

Your task:
Extract only research-specific metadata from the provided academic paper content.

Global rules:
1. Return valid JSON only.
2. Do not return markdown, code fences, comments, or explanation text.
3. Do not use outside knowledge.
4. Use only the provided paper content.
5. Do not infer or guess missing facts.
6. Do not generate title, authors, year, venue, DOI, or other base bibliographic metadata.
7. Keep all top-level keys exactly as required by the schema.
8. If a field is uncertain, weakly supported, or missing evidence, return null or empty lists instead of guessing.
9. Every non-null scalar value or non-empty list must have supporting evidence.
10. Do not fabricate page numbers or section names. Use null when unavailable.
11. Keep extracted values concise, factual, normalized, and compact.
12. The response MUST be a complete valid JSON object. If output is too long, aggressively shorten all fields instead of truncating JSON.

Required output schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Field-specific limits:
- problem.value: one concise sentence or null
- problem.evidence: at most 1 item
- method.value: one concise sentence or null
- method.evidence: at most 1 item
- contributions.value: 0 to 3 short strings
- contributions.evidence: each contribution must have exactly 1 evidence item
- limitations.value: 0 to 2 short strings
- limitations.evidence: each limitation must have exactly 1 evidence item
- evaluation_setup.value.datasets: at most 3 dataset names
- evaluation_setup.value.metrics: at most 4 metric names
- evaluation_setup.value.benchmarks: at most 3 benchmark/baseline names
- evaluation_setup.evidence: at most 1 item

Evidence rules:
- snippet must be an exact short quote from paper text
- if value is null or empty, evidence must be []
- contributions and limitations items cannot share fake evidence

Field interpretation:
- problem: the research problem/gap/task addressed by the paper
- method: the main technical approach proposed by the paper
- contributions: explicit claims/findings/main additions by the paper
- limitations: explicit weaknesses, assumptions, constraints, or future-work caveats
- evaluation_setup: datasets/metrics/benchmarks explicitly mentioned in evaluation context

Prompt version: {PROMPT_VERSION}-gemini

Paper content:
{input_text}
        """.strip()

        return instructions

    def build_extraction_prompt_gemma(self, input_text: str) -> str:
        output_shape = self._get_schema_repair_shape()

        instructions = f"""
You are an academic metadata extraction model running in strict JSON mode.

PRIMARY OBJECTIVE:
Extract research metadata from PAPER_CONTENT using this exact top-level shape:
{json.dumps(output_shape, ensure_ascii=False, indent=2)}

HARD OUTPUT RULES:
1. Return valid JSON only.
2. Use exactly 5 top-level keys: problem, method, contributions, limitations, evaluation_setup.
3. Never output other top-level keys (title, authors, abstract, venue, year, doi, etc.).
4. Never output type placeholders such as "string", "string | null", "integer", "integer | null".
5. If uncertain, output null or [] instead of guessing.

FIELD BEHAVIOR:
- problem.value: one short sentence describing the main task/problem.
- method.value: one short sentence describing the proposed method/model.
- contributions: up to 3 concrete contribution claims.
- limitations: up to 2 limitations/assumptions/future-work caveats.
- evaluation_setup: include datasets/metrics/benchmarks only when explicitly stated.

RECALL RULES (IMPORTANT):
1. Do not return contributions: [] when abstract/introduction clearly states claims (e.g., "we propose", "we present", "we show", "we achieve").
2. Prefer 2-3 contribution items when supported.
3. Prefer at least 1 limitation item when paper mentions assumptions, constraints, failure cases, resource costs, or future work.
4. If no dedicated "limitations" section exists, infer conservative limitations from explicit constraint language in the text.

ANTI-NOISE RULES (CRITICAL):
1. Do not copy long abstract paragraphs into contributions or limitations.
2. Do not output OCR-corrupted text (merged words without spaces).
3. Do not output random metric dumps as contributions unless tied to a clear claim.
4. Keep every value concise and specific.
5. If text is noisy or unrelated, drop it.

EVIDENCE RULES:
1. Every non-null scalar/list item must include evidence.
2. Evidence snippet must be literal text from paper and short (<=120 chars preferred).
3. If evidence is weak or missing, drop item or set null.
4. Page/section may be null if unknown.

CONTRIBUTIONS FILTER:
- GOOD: "Introduces attention-only Transformer architecture."
- BAD: full abstract copied as one contribution.

LIMITATIONS FILTER:
- Prefer explicit caveats from limitations/discussion/future-work context.
- If no explicit limitation sentence exists, you may use clearly implied constraints (compute cost, data dependency, domain assumptions, robustness caveats) from the provided text.
- Never invent facts outside PAPER_CONTENT.

FINAL CHECKLIST:
1. Exactly 5 top-level keys.
2. No irrelevant bibliographic keys.
3. Contributions are concise claims, not copied paragraphs.
4. Limitations are concise caveats grounded in text.
5. Avoid empty contributions/limitations when supported by PAPER_CONTENT.

Prompt version: {PROMPT_VERSION}-gemma

PAPER_CONTENT:
{input_text}
        """.strip()

        return instructions

    def build_extraction_prompt(self, input_text: str) -> str:
        # Backward-compatible alias: default extraction chain is Gemini.
        return self.build_extraction_prompt_gemini(input_text)

    def build_schema_repair_prompt_gemini(
        self,
        broken_result: Any,
        input_text: str | None = None,
    ) -> str:
        shape = self._get_schema_repair_shape()

        broken_json = (
            broken_result
            if isinstance(broken_result, str)
            else json.dumps(broken_result, ensure_ascii=False, indent=2)
        )

        instructions = f"""
You are a strict JSON schema repair assistant.

Task:
Re-extract research metadata from PAPER_CONTENT and output JSON that matches REQUIRED_SHAPE exactly.
INPUT_JSON is only a noisy hint and may contain wrong keys.

Rules:
1. Return valid JSON only.
2. Keep only top-level keys: problem, method, contributions, limitations, evaluation_setup.
3. Remove unrelated keys (title, authors, abstract, venue, year, doi, etc.).
4. Do not invent new facts.
5. If data is missing, use null or empty lists.
6. Ensure every non-null scalar and non-empty list item has evidence.
7. Never output placeholders like "string" or "string | null".

REQUIRED_SHAPE:
{json.dumps(shape, ensure_ascii=False, indent=2)}

PAPER_CONTENT:
{input_text or ""}

INPUT_JSON:
{broken_json}

Return repaired JSON only.
        """.strip()

        return instructions

    def build_schema_repair_prompt_gemma(
        self,
        broken_result: Any,
        input_text: str | None = None,
    ) -> str:
        shape = self._get_schema_repair_shape()

        broken_json = (
            broken_result
            if isinstance(broken_result, str)
            else json.dumps(broken_result, ensure_ascii=False, indent=2)
        )

        instructions = f"""
You are a strict JSON repair + re-extraction model for Gemma.

TASK:
Produce final JSON with exact top-level keys:
problem, method, contributions, limitations, evaluation_setup.

Use PAPER_CONTENT as source of truth.
INPUT_JSON can be noisy; ignore it when low quality or irrelevant.

REQUIRED_SHAPE:
{json.dumps(shape, ensure_ascii=False, indent=2)}

STRICT RULES:
1. Return valid JSON only.
2. Never output bibliographic keys (title/authors/abstract/year/venue/doi).
3. Never output placeholder literals ("string", "string | null", ...).
4. Contributions must be concise contribution claims (up to 3 items), not copied abstract blocks.
5. Avoid returning contributions: [] if PAPER_CONTENT clearly contains contribution claims.
6. Limitations should include explicit caveats/assumptions/future-work, and may include clearly implied constraints from text.
7. Drop OCR-corrupted/no-space text and irrelevant content.
8. Every non-null scalar/list item must include evidence snippet.
9. If evidence is weak, keep only conservative, well-supported items.

PAPER_CONTENT:
{input_text or ""}

INPUT_JSON:
{broken_json}

Return repaired JSON only.
        """.strip()

        return instructions

    def build_schema_repair_prompt(
        self,
        broken_result: Any,
        input_text: str | None = None,
    ) -> str:
        # Backward-compatible alias: default repair chain is Gemini.
        return self.build_schema_repair_prompt_gemini(
            broken_result,
            input_text=input_text,
        )
