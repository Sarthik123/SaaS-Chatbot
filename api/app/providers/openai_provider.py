"""OpenAI providers (optional) - STUBS for Phase 0.

Same idea as the Cloudflare stubs: creating them never fails, using them raises a clear
ProviderNotConfiguredError. The real calls arrive in Phase 2.
"""

from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    LLMResult,
    ProviderNotConfiguredError,
    not_configured_message,
)

_LABEL = "OpenAI"


def _missing(api_key: str, model: str, model_env_name: str) -> list[str]:
    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not model:
        missing.append(model_env_name)
    return missing


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, dim: int):
        self._missing = _missing(api_key, model, "EMBEDDING_MODEL")
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderNotConfiguredError(
            not_configured_message(f"{_LABEL} embeddings", self._missing)
        )


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str):
        self._missing = _missing(api_key, model, "LLM_MODEL")
        self.model = model

    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        raise ProviderNotConfiguredError(
            not_configured_message(f"{_LABEL} language model", self._missing)
        )
