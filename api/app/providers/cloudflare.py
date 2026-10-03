"""Cloudflare Workers AI providers, called over Cloudflare's REST API.

Default models (chosen from Cloudflare's current model list; the reasons are in
docs/DECISIONS.md):
  * embeddings: @cf/baai/bge-base-en-v1.5  (768 numbers per text, up to 512 tokens of input)
  * answers:    @cf/meta/llama-3.2-3b-instruct  (small, cheap, follows instructions)

Settings come from environment variables: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN and
optionally EMBEDDING_MODEL / LLM_MODEL. A provider can be created with everything empty (so the
app always starts); using it then raises a clear ProviderNotConfiguredError.

Request/response shapes used (from Cloudflare's documentation):
  embeddings  POST .../ai/run/<model>   body {"text": [...]}
                                        reply {"result": {"data": [[...], ...]}}
  chat        POST .../ai/run/<model>   body {"messages": [...], "max_tokens": N}
                                        reply {"result": {"response": "...", "usage": {
                                               "prompt_tokens": N, "completion_tokens": N}}}
"""

import json
import re

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

API_BASE = "https://api.cloudflare.com/client/v4"
DEFAULT_EMBEDDING_MODEL = "@cf/baai/bge-base-en-v1.5"
DEFAULT_EMBEDDING_DIM = 768
DEFAULT_LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"

_LABEL = "Cloudflare Workers AI"
_ACCOUNT_ID = re.compile(r"^[A-Za-z0-9]{1,64}$")


def _missing(account_id: str, api_token: str, model: str, model_env_name: str) -> list[str]:
    missing = []
    if not account_id:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not api_token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not model:
        missing.append(model_env_name)
    return missing


def _unwrap(data: dict) -> dict:
    """Cloudflare wraps every answer as {"success": ..., "errors": [...], "result": {...}}."""
    if data.get("success") is False:
        errors = data.get("errors") or []
        first = errors[0] if errors else {}
        message = first.get("message") if isinstance(first, dict) else str(first)
        raise ProviderResponseError(f"{_LABEL} reported an error: {message or 'no details'}.")
    result = data.get("result")
    if not isinstance(result, dict):
        raise ProviderResponseError(f"{_LABEL} sent a reply without a result.")
    return result


class _CloudflareBase:
    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        model_env_name: str,
        *,
        client: httpx.Client | None,
        timeout: float,
        retry_delay: float,
    ):
        self._account_id = account_id
        self._api_token = api_token
        self._missing = _missing(account_id, api_token, model, model_env_name)
        self._client = client or httpx.Client(timeout=timeout)
        self._retry_delay = retry_delay

    def _run(self, model: str, body: dict, what: str) -> dict:
        if self._missing:
            raise ProviderNotConfiguredError(
                not_configured_message(f"{_LABEL} {what}", self._missing)
            )
        if not _ACCOUNT_ID.match(self._account_id):
            raise ProviderNotConfiguredError(
                f"{_LABEL} {what} is not configured: CLOUDFLARE_ACCOUNT_ID should be letters and "
                "digits only (copy it again from the Cloudflare dashboard)."
            )
        data = post_json(
            self._client,
            f"{API_BASE}/accounts/{self._account_id}/ai/run/{model}",
            headers={"Authorization": f"Bearer {self._api_token}"},
            body=body,
            label=f"{_LABEL} {what}",
            retry_delay=self._retry_delay,
        )
        return _unwrap(data)


class CloudflareEmbeddingProvider(_CloudflareBase, EmbeddingProvider):
    name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        dim: int,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        retry_delay: float = 1.0,
    ):
        super().__init__(
            account_id,
            api_token,
            model,
            "EMBEDDING_MODEL",
            client=client,
            timeout=timeout,
            retry_delay=retry_delay,
        )
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts and not self._missing:
            return []
        result = self._run(self.model, {"text": texts}, "embeddings")
        vectors = result.get("data")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ProviderResponseError(f"{_LABEL} embeddings: expected one vector per text.")
        cleaned: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self.dim:
                size = len(vector) if isinstance(vector, list) else "no"
                raise ProviderResponseError(
                    f"{_LABEL} embeddings: the model returned {size} numbers per text but "
                    f"EMBEDDING_DIM is {self.dim}. Set EMBEDDING_DIM to the model's real size."
                )
            cleaned.append([float(value) for value in vector])
        return cleaned


class CloudflareLLMProvider(_CloudflareBase, LLMProvider):
    name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        retry_delay: float = 1.0,
    ):
        super().__init__(
            account_id,
            api_token,
            model,
            "LLM_MODEL",
            client=client,
            timeout=timeout,
            retry_delay=retry_delay,
        )
        self.model = model

    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_output_tokens,
            "temperature": 0,  # as repeatable as the model allows
        }
        result = self._run(self.model, body, "language model")
        text = result.get("response")
        if isinstance(text, (dict, list)):  # some models return already-parsed JSON
            text = json.dumps(text)
        if not isinstance(text, str):
            raise ProviderResponseError(f"{_LABEL} language model: the reply had no text.")
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        return LLMResult(
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            model=self.model,
        )
