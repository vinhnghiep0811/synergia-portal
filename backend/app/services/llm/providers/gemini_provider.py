# DEPRECATED: Provider này không còn được sử dụng. Hệ thống đã chuyển sang OpenRouter
# cho đa model. Giữ lại chỉ để tham khảo. Mọi import sẽ bị factory chặn.

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_AUTO_RETRY_DELAY_SECONDS,
    GEMINI_AUTO_RETRY_MAX_ATTEMPTS,
    GEMINI_FALLBACK_TO_OLLAMA,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_REPEAT_PENALTY,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
)
from app.services.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)
GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiCallFailedError(RuntimeError):
    """Raised when Gemini API cannot be called successfully after retries."""


class GeminiLLMProvider(BaseLLMProvider):
    _call_count = 0

    def __init__(
        self,
        model_name: str | None = None,
        retry_attempts: int | None = None,
        request_timeout_seconds: int | None = None,
        fallback_timeout_seconds: int | None = None,
        provider_alias: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip() or GEMINI_API_KEY
        self.provider_alias = (provider_alias or "gemini").strip() or "gemini"
        normalized_model = (model_name or "").strip()
        self.model = normalized_model or GEMINI_MODEL
        self.base_url = (base_url or "").strip().rstrip("/") or GEMINI_DEFAULT_BASE_URL
        self.extra_params = extra_params if isinstance(extra_params, dict) else None
        self.temperature = GEMINI_TEMPERATURE
        self.max_output_tokens = GEMINI_MAX_OUTPUT_TOKENS

        self.retry_attempts = (
            max(1, int(retry_attempts))
            if retry_attempts is not None
            else GEMINI_AUTO_RETRY_MAX_ATTEMPTS
        )
        self.retry_delay_seconds = GEMINI_AUTO_RETRY_DELAY_SECONDS
        self.request_timeout_seconds = (
            max(1, int(request_timeout_seconds))
            if request_timeout_seconds is not None
            else 120
        )
        self.enable_ollama_fallback = GEMINI_FALLBACK_TO_OLLAMA
        self.ollama_base_url = OLLAMA_BASE_URL
        self.ollama_model = OLLAMA_MODEL
        self.ollama_timeout_seconds = (
            max(1, int(fallback_timeout_seconds))
            if fallback_timeout_seconds is not None
            else OLLAMA_TIMEOUT_SECONDS
        )
        self.ollama_temperature = OLLAMA_TEMPERATURE
        self.ollama_num_predict = OLLAMA_NUM_PREDICT
        self.ollama_num_ctx = OLLAMA_NUM_CTX
        self.ollama_top_p = OLLAMA_TOP_P
        self.ollama_repeat_penalty = OLLAMA_REPEAT_PENALTY

        if not self.api_key and not self.enable_ollama_fallback:
            raise ValueError("GEMINI_API_KEY is missing.")

        if not self.api_key and self.enable_ollama_fallback:
            logger.warning(
                "[GEMINI CONFIG] GEMINI_API_KEY is missing. Ollama fallback will be used."
            )

    def extract_metadata(self, prompt: str, fallback_prompt: str | None = None) -> Dict[str, Any]:
        provider_result = self._extract_from_provider(prompt, fallback_prompt=fallback_prompt)

        raw_text = provider_result["raw_text"]
        usage = provider_result.get("usage") or {}
        finish_reason = provider_result.get("finish_reason")
        provider_name = provider_result.get("provider") or self.provider_alias
        model_name = provider_result.get("model") or self.model

        import os
        try:
            os.makedirs("/tmp", exist_ok=True)
            with open("/tmp/llm_raw_output.txt", "w", encoding="utf-8") as f:
                f.write(raw_text)
        except Exception as save_err:
            logger.warning("[LLM OUTPUT SAVE] Failed to save raw output: %s", save_err)

        logger.info(
            "[LLM OUTPUT PREVIEW] provider=%s model=%s chars=%s preview=%s",
            provider_name,
            model_name,
            len(raw_text),
            raw_text[:1000],
        )
        logger.info(
            "[LLM OUTPUT TAIL] provider=%s model=%s last_1000_chars=\n%s",
            provider_name,
            model_name,
            raw_text[-1000:],
        )
        logger.warning(
            "[LLM META] provider=%s model=%s finish_reason=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s output_chars=%s",
            provider_name,
            model_name,
            finish_reason,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
            len(raw_text),
        )

        result_json = self._safe_parse_json(raw_text)

        if finish_reason in {"MAX_TOKENS", "length"}:
            logger.error(
                "[LLM TRUNCATED] provider=%s model=%s finish_reason=%s output_tail=\n%s",
                provider_name,
                model_name,
                finish_reason,
                raw_text[-1500:],
            )
            raise ValueError(
                f"{provider_name} output was truncated due to max output tokens"
            )

        if result_json is None:
            logger.error(
                "[LLM INVALID JSON] provider=%s model=%s output_head=\n%s\n\noutput_tail=\n%s",
                provider_name,
                model_name,
                raw_text[:1000],
                raw_text[-1000:],
            )

        return {
            "result_json": result_json,
            "raw_text": raw_text,
            "usage": usage,
            "provider": provider_name,
            "model": model_name,
            "finish_reason": finish_reason,
        }

    def _extract_from_provider(self, prompt: str, fallback_prompt: str | None = None) -> Dict[str, Any]:
        try:
            return self._extract_via_gemini(prompt)
        except GeminiCallFailedError as gemini_error:
            if not self.enable_ollama_fallback:
                raise

            logger.warning(
                "[GEMINI FALLBACK] reason=%s fallback_provider=ollama fallback_model=%s fallback_base_url=%s",
                str(gemini_error),
                self.ollama_model,
                self.ollama_base_url,
            )

            return self._extract_via_ollama(fallback_prompt or prompt)

    def _extract_via_gemini(self, prompt: str) -> Dict[str, Any]:
        raw_response = self._call_gemini(prompt)
        usage = raw_response.get("usageMetadata") or {}
        candidates = raw_response.get("candidates") or []
        finish_reason = candidates[0].get("finishReason") if candidates else None

        return {
            "raw_text": self._extract_text_from_response(raw_response),
            "usage": {
                "prompt_tokens": usage.get("promptTokenCount"),
                "completion_tokens": usage.get("candidatesTokenCount"),
                "total_tokens": usage.get("totalTokenCount"),
            },
            "provider": self.provider_alias,
            "model": self.model,
            "finish_reason": finish_reason,
        }

    def _extract_via_ollama(self, prompt: str) -> Dict[str, Any]:
        endpoint = f"{self.ollama_base_url}/api/generate"

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.ollama_temperature,
                "num_predict": self.ollama_num_predict,
                "num_ctx": self.ollama_num_ctx,
                "top_p": self.ollama_top_p,
                "repeat_penalty": self.ollama_repeat_penalty,
            },
        }

        request = urllib.request.Request(
            url=endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.ollama_timeout_seconds) as response:
                body = response.read().decode("utf-8")
                logger.warning("[OLLAMA RESPONSE] status=200 body_preview=%s", body[:300])
                response_json = json.loads(body)

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                error_body = str(e)

            raise RuntimeError(
                f"Ollama fallback HTTPError status={e.code} body={error_body}"
            ) from e

        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama fallback URLError: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Ollama fallback unexpected error: {e}") from e

        raw_text = (response_json.get("response") or "").strip()
        if not raw_text:
            raise RuntimeError("Ollama fallback returned empty response")

        prompt_tokens = response_json.get("prompt_eval_count")
        completion_tokens = response_json.get("eval_count")
        total_tokens = None

        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total_tokens = prompt_tokens + completion_tokens

        return {
            "raw_text": raw_text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "provider": "ollama",
            "model": self.ollama_model,
            "finish_reason": response_json.get("done_reason"),
        }

    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise GeminiCallFailedError("GEMINI_API_KEY is missing")

        endpoint = f"{self.base_url}/models/{self.model}:generateContent"

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
                "thinkingConfig": {
                    "thinkingBudget": 0
                },
            },
        }
        payload = self._apply_extra_params(payload)

        last_error: Exception | None = None
        attempt_used = 0

        for attempt in range(1, self.retry_attempts + 1):
            attempt_used = attempt
            GeminiLLMProvider._call_count += 1

            logger.warning(
                "[GEMINI CALL] count=%s attempt=%s/%s model=%s prompt_chars=%s",
                GeminiLLMProvider._call_count,
                attempt,
                self.retry_attempts,
                self.model,
                len(prompt),
            )
            logger.debug("[GEMINI PROMPT PREVIEW]\n%s", prompt[:500])

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
                with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
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
                    "[GEMINI ERROR] attempt=%s/%s status=%s body=%s",
                    attempt,
                    self.retry_attempts,
                    e.code,
                    error_body[:500],
                )

                is_retriable = e.code == 429 or 500 <= e.code < 600
                last_error = RuntimeError(
                    f"Gemini API HTTPError status={e.code} body={error_body}"
                )

                if is_retriable and attempt < self.retry_attempts:
                    logger.warning(
                        "[GEMINI RETRY] reason=http_status_%s attempt=%s/%s retry_in_seconds=%s",
                        e.code,
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

            except urllib.error.URLError as e:
                last_error = RuntimeError(f"Gemini API URLError: {e}")

                if attempt < self.retry_attempts:
                    logger.warning(
                        "[GEMINI RETRY] reason=url_error attempt=%s/%s retry_in_seconds=%s error=%s",
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                        str(e),
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

            except Exception as e:
                last_error = RuntimeError(f"Gemini API unexpected error: {e}")

                if attempt < self.retry_attempts:
                    logger.warning(
                        "[GEMINI RETRY] reason=unexpected_error attempt=%s/%s retry_in_seconds=%s error=%s",
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                        str(e),
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

        if last_error is None:
            last_error = RuntimeError("Gemini API call failed with unknown error")

        raise GeminiCallFailedError(
            f"Gemini API failed after {attempt_used} attempt(s): {last_error}"
        ) from last_error

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

    def _apply_extra_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.extra_params:
            return payload

        generation_override = self.extra_params.get("generationConfig")
        if isinstance(generation_override, dict):
            payload["generationConfig"].update(generation_override)

        for key, value in self.extra_params.items():
            if key in {"generationConfig", "contents"}:
                continue
            payload[key] = value

        return payload

    def _safe_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_text)
        except Exception:
            return None
