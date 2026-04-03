from app.core.config import LLM_PROVIDER
from app.services.llm.providers.base import BaseLLMProvider
from app.services.llm.providers.gemini_provider import GeminiLLMProvider


class LLMProviderFactory:
    @staticmethod
    def create(provider_name: str | None = None) -> BaseLLMProvider:
        selected = (provider_name or LLM_PROVIDER or "gemini").lower().strip()

        if selected == "gemini":
            return GeminiLLMProvider()

        raise ValueError(f"Unsupported LLM provider: {selected}")