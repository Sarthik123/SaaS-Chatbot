"""OpenAI providers (optional). Chosen with LLM_PROVIDER=openai.

There is no default model here: set LLM_MODEL and EMBEDDING_MODEL (and EMBEDDING_DIM) yourself,
because OpenAI's model list changes often. Use a small, cheap chat model and an embedding model.

IMPORTANT: this path is only covered by tests that use fake HTTP replies. It has not been run
against the live OpenAI service in this project.

Request/response shapes (OpenAI REST API):
  embeddings  POST /v1/embeddings
              body {"model", "input": [...]}  reply {"data": [{"embedding": [...]}, ...]}
  chat        POST /v1/chat/completions
              body {"model", "messages", ...}
              reply {"choices": [{"message": {"content": "..."}}], "usage": {...}}
For the text-embedding-3 models we also send "dimensions" so the size matches EMBEDDING_DIM.
"""

import httpx

from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    LLMResult,
    ProviderNotConfiguredError,
    ProviderResponseError,
    not_configured_message,
)
from app.providers.http import post_json

API_BASE = "https://api.openai.com/v1"
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

    def __init__(
        self,
        api_key: str,
        model: str,
        dim: int,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        retry_delay: float = 1.0,
    ):
        self._api_key = api_key
        self._missing = _missing(api_key, model, "EMBEDDING_MODEL")
        self._client = client or httpx.Client(timeout=timeout)
        self._retry_delay = retry_delay
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._missing:
            raise ProviderNotConfiguredError(
                not_configured_message(f"{_LABEL} embeddings", self._missing)
            )
        if not texts:
            return []
        body: dict = {"model": self.model, "input": texts}
        if self.model.startswith("text-embedding-3"):
            body["dimensions"] = self.dim
        data = post_json(
            self._client,
            f"{API_BASE}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            body=body,
            label=f"{_LABEL} embeddings",
            retry_delay=self._retry_delay,
        )
        items = data.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise ProviderResponseError(f"{_LABEL} embeddings: expected one vector per text.")
        # OpenAI says each item has an "index"; sort so the order always matches the input.
        items = sorted(
            items, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0
        )
        vectors: list[list[float]] = []
        for item in items:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or len(vector) != self.dim:
                size = len(vector) if isinstance(vector, list) else "no"
                raise ProviderResponseError(
                    f"{_LABEL} embeddings: the model returned {size} numbers per text but "
                    f"EMBEDDING_DIM is {self.dim}. Set EMBEDDING_DIM to the model's real size."
                )
            vectors.append([float(value) for value in vector])
        return vectors


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        retry_delay: float = 1.0,
    ):
        self._api_key = api_key
        self._missing = _missing(api_key, model, "LLM_MODEL")
        self._client = client or httpx.Client(timeout=timeout)
        self._retry_delay = retry_delay
        self.model = model

    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        if self._missing:
            raise ProviderNotConfiguredError(
                not_configured_message(f"{_LABEL} language model", self._missing)
            )
        data = post_json(
            self._client,
            f"{API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            body={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": max_output_tokens,
                "response_format": {"type": "json_object"},
            },
            label=f"{_LABEL} language model",
            retry_delay=self._retry_delay,
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderResponseError(
                f"{_LABEL} language model: the reply had no text."
            ) from error
        if not isinstance(text, str):
            raise ProviderResponseError(f"{_LABEL} language model: the reply had no text.")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return LLMResult(
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            model=self.model,
        )
