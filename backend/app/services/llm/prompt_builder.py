import json
from typing import Any

from app.services.llm.constants import PROMPT_VERSION
from app.services.llm.prompt_templates import DEFAULT_PROMPT_TEMPLATES


class LLMPromptBuilder:
    def __init__(self, templates: dict[str, str] | None = None) -> None:
        self._templates = templates or {}

    def _get_template(self, key: str) -> str:
        return self._templates.get(key) or DEFAULT_PROMPT_TEMPLATES[key]

    def _render_template(self, template: str, values: dict[str, str]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered.strip()

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
        template = self._get_template("extraction_prompt_primary")
        return self._render_template(
            template,
            {
                "schema": json.dumps(schema, ensure_ascii=False, indent=2),
                "prompt_version": f"{PROMPT_VERSION}-gemini",
                "input_text": input_text,
            },
        )

    def build_extraction_prompt_gemma(self, input_text: str) -> str:
        output_shape = self._get_schema_repair_shape()
        template = self._get_template("extraction_prompt_fallback")
        return self._render_template(
            template,
            {
                "output_shape": json.dumps(output_shape, ensure_ascii=False, indent=2),
                "prompt_version": f"{PROMPT_VERSION}-gemma",
                "input_text": input_text,
            },
        )

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

        template = self._get_template("schema_repair_prompt_primary")
        return self._render_template(
            template,
            {
                "shape": json.dumps(shape, ensure_ascii=False, indent=2),
                "input_text": input_text or "",
                "broken_json": broken_json,
                "prompt_version": f"{PROMPT_VERSION}-gemini-repair",
            },
        )

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

        template = self._get_template("schema_repair_prompt_fallback")
        return self._render_template(
            template,
            {
                "shape": json.dumps(shape, ensure_ascii=False, indent=2),
                "input_text": input_text or "",
                "broken_json": broken_json,
                "prompt_version": f"{PROMPT_VERSION}-gemma-repair",
            },
        )

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
