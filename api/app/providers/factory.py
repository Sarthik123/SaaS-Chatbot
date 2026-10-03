"""Picks the right provider for the LLM_PROVIDER setting (cloudflare, openai or fake)."""

from app.config import Settings
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.cloudflare import CloudflareEmbeddingProvider, CloudflareLLMProvider
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.providers.openai_provider import OpenAIEmbeddingProvider, OpenAILLMProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.llm_provider == "fake":
        return FakeEmbeddingProvider(dim=settings.embedding_dim)
    if settings.llm_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )
    return CloudflareEmbeddingProvider(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token.get_secret_value(),
        model=settings.embedding_model,
        dim=settings.embedding_dim,
    )


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model,
        )
    return CloudflareLLMProvider(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token.get_secret_value(),
        model=settings.llm_model,
    )
