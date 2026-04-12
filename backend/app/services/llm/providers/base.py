from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLMProvider(ABC):
    @abstractmethod
    def extract_metadata(self, prompt: str, fallback_prompt: str | None = None) -> Dict[str, Any]:
        """
        Return standardized provider output shape:
        {
            "result_json": dict | None,
            "raw_text": str,
            "usage": {
                "prompt_tokens": int | None,
                "completion_tokens": int | None,
                "total_tokens": int | None,
            },
            "provider": str,
            "model": str,
            "finish_reason": str | None,
        }
        """
        raise NotImplementedError