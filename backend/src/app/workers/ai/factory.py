"""
AI provider factory.
Change AI_PROVIDER in .env to switch providers — zero code changes.
Supported: openai | ollama | gemini
"""
from app.core.config import settings
from app.workers.ai.base import AIProvider

_OLLAMA_DEFAULT_URL = "http://localhost:11434/v1"
_OLLAMA_DEFAULT_MODEL = "llama3.1:8b"


def get_ai_provider() -> AIProvider:
    provider = settings.AI_PROVIDER.lower()

    if provider == "openai":
        from app.workers.ai.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
        )

    if provider == "ollama":
        from app.workers.ai.ollama_provider import OllamaProvider
        return OllamaProvider(
            model=settings.AI_MODEL or _OLLAMA_DEFAULT_MODEL,
            base_url=settings.AI_BASE_URL or _OLLAMA_DEFAULT_URL,
        )

    if provider == "gemini":
        from app.workers.ai.gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
        )

    raise ValueError(
        f"Unknown AI provider '{provider}'. Supported: openai, ollama, gemini. "
        "Set AI_PROVIDER in .env."
    )
