import os
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.llm.providers.openrouter_provider import OpenRouterLLMProvider


class OpenRouterJsonParseTests(unittest.TestCase):
    def test_safe_parse_json_keeps_raw_json_behavior(self) -> None:
        result = OpenRouterLLMProvider._safe_parse_json('{"problem": {"value": "ok"}}')

        self.assertEqual(result, {"problem": {"value": "ok"}})

    def test_safe_parse_json_strips_markdown_code_fence(self) -> None:
        raw_text = """```json
{
  "problem": {
    "value": "Aircraft electrification reduces aviation emissions.",
    "evidence": []
  }
}
```"""

        result = OpenRouterLLMProvider._safe_parse_json(raw_text)

        self.assertEqual(
            result,
            {
                "problem": {
                    "value": "Aircraft electrification reduces aviation emissions.",
                    "evidence": [],
                }
            },
        )

    def test_safe_parse_json_extracts_first_object_from_text(self) -> None:
        raw_text = 'Here is the JSON:\n{"method": {"value": "review", "evidence": []}}\nDone.'

        result = OpenRouterLLMProvider._safe_parse_json(raw_text)

        self.assertEqual(result, {"method": {"value": "review", "evidence": []}})

    def test_safe_parse_json_returns_none_for_invalid_output(self) -> None:
        result = OpenRouterLLMProvider._safe_parse_json("not json")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
