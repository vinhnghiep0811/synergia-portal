import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)
from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_OUTPUT_TOKENS,
)
from app.services.llm.providers.base import BaseLLMProvider


class GeminiLLMProvider(BaseLLMProvider):
    _call_count = 0
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL
        self.temperature = GEMINI_TEMPERATURE
        self.max_output_tokens = GEMINI_MAX_OUTPUT_TOKENS

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing.")

    def extract_metadata(self, prompt: str) -> Dict[str, Any]:
        raw_response = self._call_gemini(prompt)
        raw_text = self._extract_text_from_response(raw_response)
        result_json = self._safe_parse_json(raw_text)

        usage = raw_response.get("usageMetadata") or {}
        candidates = raw_response.get("candidates") or []
        finish_reason = candidates[0].get("finishReason") if candidates else None

        return {
            "result_json": result_json,
            "raw_text": raw_text,
            "usage": {
                "prompt_tokens": usage.get("promptTokenCount"),
                "completion_tokens": usage.get("candidatesTokenCount"),
                "total_tokens": usage.get("totalTokenCount"),
            },
            "provider": "gemini",
            "model": self.model,
            "finish_reason": finish_reason,
        }

    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        GeminiLLMProvider._call_count += 1

        logger.warning(
            "[GEMINI CALL] count=%s model=%s prompt_chars=%s",
            GeminiLLMProvider._call_count,
            self.model,
            len(prompt),
        )

        # debug thêm nếu cần
        logger.debug("[GEMINI PROMPT PREVIEW]\n%s", prompt[:500])
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        request = urllib.request.Request(
            url=endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
                logger.warning("[GEMINI RESPONSE] status=200 body_preview=%s", body[:300])
                return json.loads(body)

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                error_body = str(e)

            logger.error(
                "[GEMINI ERROR] status=%s body=%s",
                e.code,
                error_body[:500],
            )

            raise RuntimeError(
                f"Gemini API HTTPError status={e.code} body={error_body}"
            ) from e

        except urllib.error.URLError as e:
            raise RuntimeError(f"Gemini API URLError: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Gemini API unexpected error: {e}") from e

    def _extract_text_from_response(self, response_json: Dict[str, Any]) -> str:
        candidates = response_json.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini response has no candidates.")

        content = (candidates[0].get("content") or {})
        parts = content.get("parts") or []

        texts: list[str] = []
        for part in parts:
            text = part.get("text")
            if text:
                texts.append(text)

        raw_text = "\n".join(texts).strip()
        if not raw_text:
            raise ValueError("Gemini response does not contain text output.")

        return raw_text

    def _safe_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_text)
        except Exception:
            return None