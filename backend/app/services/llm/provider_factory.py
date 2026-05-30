from app.core.config import LLM_PROVIDER
from app.services.llm.providers.base import BaseLLMProvider
from app.services.llm.providers.ollama_provider import OllamaLLMProvider
from app.services.llm.providers.openrouter_provider import OpenRouterLLMProvider


class LLMProviderFactory:
    @staticmethod
    def create(
        provider_name: str | None = None,
        model_name: str | None = None,
        retry_limit: int | None = None,
        timeout_seconds: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_params: dict | None = None,
    ) -> BaseLLMProvider:
        selected = (provider_name or LLM_PROVIDER or "openrouter").lower().strip()
        if selected in {"gemini", "deepseek"}:
            selected = "openrouter"

        if selected == "ollama":
            return OllamaLLMProvider(
                model_name=model_name,
                timeout_seconds=timeout_seconds,
                base_url=base_url,
                extra_params=extra_params,
            )

        if selected == "openrouter":
            return OpenRouterLLMProvider(
                model_name=model_name,
                retry_attempts=retry_limit,
                request_timeout_seconds=timeout_seconds,
                fallback_timeout_seconds=timeout_seconds,
                provider_alias=selected,
                api_key=api_key,
                base_url=base_url,
                extra_params=extra_params,
            )

        raise ValueError(
            f"Unsupported LLM provider '{selected}'. Please add a provider class for it."
        )
