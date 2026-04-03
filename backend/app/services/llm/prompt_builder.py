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
            "contributions": [
                {
                    "value": "string",
                    "evidence": [
                        {
                            "snippet": "string",
                            "page": "integer | null",
                            "section": "string | null"
                        }
                    ]
                }
            ],
            "limitations": [
                {
                    "value": "string",
                    "evidence": [
                        {
                            "snippet": "string",
                            "page": "integer | null",
                            "section": "string | null"
                        }
                    ]
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
13. If multiple fields rely on the same evidence, you may reuse the same strongest short snippet.
14. Strictly keep all text extremely short (prefer <20 words per field).

Output size control rules (CRITICAL):

- Minimize verbosity at all costs
- Prefer short phrases over full sentences
- Avoid repetition across fields
- Do not restate the same idea in multiple fields
- If output risks being long, shorten all fields further
- It is better to return less information than to exceed output limit

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

Evidence rules (STRICT):

- evidence must be an array
- each evidence item must have:
  - snippet: exact quote from the text, max 80 characters
  - page: integer if recoverable, else null
  - section: section name if identifiable, else null

- always prefer the SHORTEST valid snippet
- do NOT include long sentences or paragraphs
- do NOT include multiple sentences in snippet
- if value is null or empty, evidence must be []
- For contributions and limitations:
  each item MUST have its own evidence
  do NOT share evidence across multiple items

Consistency rules:
- if a scalar value is null, its evidence must be []
- if a list value is empty, its evidence must be []
- if all evaluation_setup lists are empty, evaluation_setup.evidence must be []
- each contribution item must have its own evidence array
- each limitation item must have its own evidence array
- if an item has no strong evidence, DO NOT include that item

Field interpretation rules:
- problem: the research problem, gap, or task the paper aims to solve
- method: the main technical approach proposed by the paper
- contributions: explicit claimed contributions, findings, or main claimed additions
- limitations: explicit limitations, assumptions, weaknesses, constraints, or future-work caveats stated by the paper
- evaluation_setup: only include datasets, benchmarks, and metrics explicitly mentioned in evaluation or experiment context

Critical extraction strategy:
- Problem, method, and contributions are often found in the abstract or introduction.
- Limitations are often found near the end of the paper.
- For limitations, actively inspect sections or passages containing words like:
  "limitation", "limitations", "discussion", "future work", "conclusion", "assumption", "assumptions", "constraint", "constraints".
- Do not invent limitations from your own interpretation of the method.
- Only extract limitations if the paper states them explicitly or near-explicitly.
- If there is no clear evidence for limitations, return an empty list.

Prompt version: {PROMPT_VERSION}

Paper content:
{input_text}
        """.strip()

        return instructions