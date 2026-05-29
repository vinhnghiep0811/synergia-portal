import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from app.core.config import (
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


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(
        self,
        model_name: str | None = None,
        timeout_seconds: int | None = None,
        base_url: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        normalized_model = (model_name or "").strip()
        self.model = normalized_model or OLLAMA_MODEL
        self.base_url = (base_url or "").strip().rstrip("/") or OLLAMA_BASE_URL
        self.timeout_seconds = (
            max(1, int(timeout_seconds))
            if timeout_seconds is not None
            else OLLAMA_TIMEOUT_SECONDS
        )
        self.temperature = OLLAMA_TEMPERATURE
        self.num_predict = OLLAMA_NUM_PREDICT
        self.num_ctx = OLLAMA_NUM_CTX
        self.top_p = OLLAMA_TOP_P
        self.repeat_penalty = OLLAMA_REPEAT_PENALTY
        self.extra_params = extra_params if isinstance(extra_params, dict) else None

    def extract_metadata(self, prompt: str, fallback_prompt: str | None = None) -> Dict[str, Any]:
        del fallback_prompt
        provider_result = self._extract_via_ollama(prompt)

        raw_text = provider_result["raw_text"]
        usage = provider_result.get("usage") or {}
        finish_reason = provider_result.get("finish_reason")
        provider_name = provider_result.get("provider") or "ollama"
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

    def _extract_via_ollama(self, prompt: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx,
                "top_p": self.top_p,
                "repeat_penalty": self.repeat_penalty,
            },
        }
        if self.extra_params:
            extra_options = self.extra_params.get("options")
            if isinstance(extra_options, dict):
                payload["options"].update(extra_options)
            for key, value in self.extra_params.items():
                if key in {"options", "model", "prompt"}:
                    continue
                payload[key] = value

        request = urllib.request.Request(
            url=endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
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
                f"Ollama provider HTTPError status={e.code} body={error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama provider URLError: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Ollama provider unexpected error: {e}") from e

        raw_text = (response_json.get("response") or "").strip()
        if not raw_text:
            raise RuntimeError("Ollama provider returned empty response")

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
            "model": self.model,
            "finish_reason": response_json.get("done_reason"),
        }

    @staticmethod
    def _safe_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_text)
        except Exception:
            return None
