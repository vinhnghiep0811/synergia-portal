import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from app.services.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekCallFailedError(RuntimeError):
    """Raised when DeepSeek API cannot be called successfully after retries."""


class DeepSeekLLMProvider(BaseLLMProvider):
    _call_count = 0

    def __init__(
        self,
        model_name: str | None = None,
        retry_attempts: int | None = None,
        request_timeout_seconds: int | None = None,
        provider_alias: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.provider_alias = (provider_alias or "deepseek").strip() or "deepseek"
        normalized_model = (model_name or "").strip()
        self.model = normalized_model or "deepseek-v4-pro"
        self.base_url = (base_url or "").strip().rstrip("/") or DEEPSEEK_DEFAULT_BASE_URL
        self.extra_params = extra_params if isinstance(extra_params, dict) else None

        self.retry_attempts = max(1, int(retry_attempts)) if retry_attempts is not None else 3
        self.retry_delay_seconds = 1.0
        self.request_timeout_seconds = (
            max(1, int(request_timeout_seconds))
            if request_timeout_seconds is not None
            else 120
        )

        if not self.api_key:
            raise ValueError("DeepSeek API key is missing.")

    def extract_metadata(self, prompt: str, fallback_prompt: str | None = None) -> Dict[str, Any]:
        del fallback_prompt
        provider_result = self._extract_via_deepseek(prompt)

        raw_text = provider_result["raw_text"]
        usage = provider_result.get("usage") or {}
        finish_reason = provider_result.get("finish_reason")
        provider_name = provider_result.get("provider") or self.provider_alias
        model_name = provider_result.get("model") or self.model

        with open("/tmp/llm_raw_output.txt", "w", encoding="utf-8") as f:
            f.write(raw_text)

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

    def _extract_via_deepseek(self, prompt: str) -> Dict[str, Any]:
        raw_response = self._call_deepseek(prompt)
        choices = raw_response.get("choices") or []
        message = choices[0].get("message") if choices else None
        raw_text = (message or {}).get("content") if isinstance(message, dict) else None
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("DeepSeek response does not contain text output.")

        usage = raw_response.get("usage") or {}
        finish_reason = choices[0].get("finish_reason") if choices else None

        return {
            "raw_text": raw_text.strip(),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            "provider": self.provider_alias,
            "model": self.model,
            "finish_reason": finish_reason,
        }

    def _call_deepseek(self, prompt: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        payload = self._apply_extra_params(payload)

        last_error: Exception | None = None
        attempt_used = 0

        for attempt in range(1, self.retry_attempts + 1):
            attempt_used = attempt
            DeepSeekLLMProvider._call_count += 1

            logger.warning(
                "[DEEPSEEK CALL] count=%s attempt=%s/%s model=%s prompt_chars=%s",
                DeepSeekLLMProvider._call_count,
                attempt,
                self.retry_attempts,
                self.model,
                len(prompt),
            )

            request = urllib.request.Request(
                url=endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    logger.warning("[DEEPSEEK RESPONSE] status=200 body_preview=%s", body[:300])
                    return json.loads(body)

            except urllib.error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8")
                except Exception:
                    error_body = str(e)

                logger.error(
                    "[DEEPSEEK ERROR] attempt=%s/%s status=%s body=%s",
                    attempt,
                    self.retry_attempts,
                    e.code,
                    error_body[:500],
                )

                is_retriable = e.code == 429 or 500 <= e.code < 600
                last_error = RuntimeError(
                    f"DeepSeek API HTTPError status={e.code} body={error_body}"
                )

                if is_retriable and attempt < self.retry_attempts:
                    logger.warning(
                        "[DEEPSEEK RETRY] reason=http_status_%s attempt=%s/%s retry_in_seconds=%s",
                        e.code,
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

            except urllib.error.URLError as e:
                last_error = RuntimeError(f"DeepSeek API URLError: {e}")

                if attempt < self.retry_attempts:
                    logger.warning(
                        "[DEEPSEEK RETRY] reason=url_error attempt=%s/%s retry_in_seconds=%s error=%s",
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                        str(e),
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

            except Exception as e:
                last_error = RuntimeError(f"DeepSeek API unexpected error: {e}")

                if attempt < self.retry_attempts:
                    logger.warning(
                        "[DEEPSEEK RETRY] reason=unexpected_error attempt=%s/%s retry_in_seconds=%s error=%s",
                        attempt,
                        self.retry_attempts,
                        self.retry_delay_seconds,
                        str(e),
                    )
                    time.sleep(self.retry_delay_seconds)
                    continue

                break

        if last_error is None:
            last_error = RuntimeError("DeepSeek API call failed with unknown error")

        raise DeepSeekCallFailedError(
            f"DeepSeek API failed after {attempt_used} attempt(s): {last_error}"
        ) from last_error

    def _apply_extra_params(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.extra_params:
            return payload

        for key, value in self.extra_params.items():
            if key in {"model", "messages", "stream"}:
                continue
            payload[key] = value

        return payload

    @staticmethod
    def _safe_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_text)
        except Exception:
            return None
