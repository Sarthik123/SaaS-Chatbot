"""Cloudflare Workers AI providers - STUBS for Phase 0.

They can be created even when keys are empty (so the app always starts), but using them
raises a clear ProviderNotConfiguredError. The real REST calls arrive in Phase 2.
"""

from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    LLMResult,
    ProviderNotConfiguredError,
    not_configured_message,
)

_LABEL = "Cloudflare Workers AI"


def _missing(account_id: str, api_token: str, model: str, model_env_name: str) -> list[str]:
    missing = []
    if not account_id:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not api_token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not model:
        missing.append(model_env_name)
    return missing


class CloudflareEmbeddingProvider(EmbeddingProvider):
    name = "cloudflare"

    def __init__(self, account_id: str, api_token: str, model: str, dim: int):
        self._missing = _missing(account_id, api_token, model, "EMBEDDING_MODEL")
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderNotConfiguredError(
            not_configured_message(f"{_LABEL} embeddings", self._missing)
        )


class CloudflareLLMProvider(LLMProvider):
    name = "cloudflare"

    def __init__(self, account_id: str, api_token: str, model: str):
        self._missing = _missing(account_id, api_token, model, "LLM_MODEL")
        self.model = model

    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        raise ProviderNotConfiguredError(
            not_configured_message(f"{_LABEL} language model", self._missing)
        )
