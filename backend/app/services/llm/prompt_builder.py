import json

from app.services.llm.constants import PROMPT_VERSION


class LLMPromptBuilder:
    def build_extraction_prompt(self, input_text: str) -> str:
        schema = {
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
            "contributions": {
                "value": ["string"],
                "evidence": [
                    {
                        "snippet": "string",
                        "page": "integer | null",
                        "section": "string | null",
                    }
                ],
            },
            "limitations": {
                "value": ["string"],
                "evidence": [
                    {
                        "snippet": "string",
                        "page": "integer | null",
                        "section": "string | null",
                    }
                ],
            },
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
9. Every non-null scalar value or non-empty list must have at least one supporting evidence item.
10. Evidence snippets must come directly from the provided content and should be short, relevant, and faithful to the source text.
11. Do not fabricate page numbers or section names. Use null when unavailable.
12. Keep extracted values concise, factual, and normalized.

Required output schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Field-specific rules:
- problem.value:
  - one concise sentence if the paper clearly states the research problem, task, or objective
  - otherwise null

- method.value:
  - one concise sentence describing the main method, approach, or model
  - otherwise null

- contributions.value:
  - array of 0 to 3 short strings
  - include only contributions clearly claimed or strongly supported by the paper
  - if unclear, return []

- limitations.value:
  - array of short strings
  - include only explicit limitations, assumptions, constraints, or important caveats
  - if unavailable, return []

- evaluation_setup.value.datasets:
  - list dataset names only
  - no explanation text

- evaluation_setup.value.metrics:
  - list metric names only
  - no explanation text

- evaluation_setup.value.benchmarks:
  - list benchmark names only
  - no explanation text

Evidence rules:
- evidence must be an array
- each evidence item must have:
  - snippet: short quote-like text copied from or tightly grounded in the provided content
  - page: integer if explicitly recoverable from the provided content, else null
  - section: section name if clearly identifiable from the provided content, else null
- if value is null or an array is empty, evidence should be []

Consistency rules:
- if problem.value is null, then problem.evidence must be []
- if method.value is null, then method.evidence must be []
- if contributions.value is [], then contributions.evidence must be []
- if limitations.value is [], then limitations.evidence must be []
- if evaluation_setup.value.datasets, metrics, and benchmarks are all empty, then evaluation_setup.evidence must be []

Prompt version: {PROMPT_VERSION}

Paper content:
{input_text}
        """.strip()

        return instructions