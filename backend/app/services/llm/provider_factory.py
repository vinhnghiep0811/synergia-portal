from app.core.config import LLM_PROVIDER
from app.services.llm.providers.base import BaseLLMProvider
from app.services.llm.providers.gemini_provider import GeminiLLMProvider
from app.services.llm.providers.ollama_provider import OllamaLLMProvider


class LLMProviderFactory:
    @staticmethod
    def create(
        provider_name: str | None = None,
        model_name: str | None = None,
        retry_limit: int | None = None,
        timeout_seconds: int | None = None,
        api_key: str | None = None,
    ) -> BaseLLMProvider:
        selected = (provider_name or LLM_PROVIDER or "gemini").lower().strip()

        if selected == "ollama":
            return OllamaLLMProvider(
                model_name=model_name,
                timeout_seconds=timeout_seconds,
            )

        return GeminiLLMProvider(
            model_name=model_name,
            retry_attempts=retry_limit,
            request_timeout_seconds=timeout_seconds,
            fallback_timeout_seconds=timeout_seconds,
            provider_alias=selected,
            api_key=api_key,
        )
