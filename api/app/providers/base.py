"""The two small interfaces every AI provider must follow.

Why interfaces? The rest of the app only ever talks to "an EmbeddingProvider" and
"an LLMProvider". That lets us swap Cloudflare for OpenAI, or for a free fake used in
tests, without rewriting any other code.

  * EmbeddingProvider: turns text into a list of numbers (an "embedding") that
    captures its meaning, so we can search by meaning.
  * LLMProvider: the language model that writes the answer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(RuntimeError):
    """Something went wrong talking to an AI provider. The message never contains a secret."""


class ProviderNotConfiguredError(ProviderError):
    """A real AI provider is used but a setting (key, account, model) is missing."""


class ProviderUnavailableError(ProviderError):
    """The provider did not answer in time, is rate-limiting us, or is down (we retried once)."""


class ProviderResponseError(ProviderError):
    """The provider answered, but with an error or with something we cannot use."""


def not_configured_message(label: str, missing: list[str]) -> str:
    """A clear, secret-free message that says exactly what to fix."""
    return (
        f"{label} is not configured. Set these in your .env file: "
        f"{', '.join(missing)}. (See .env.example.)"
    )


@dataclass(frozen=True)
class LLMResult:
    """What a language-model call returns."""

    text: str
    input_tokens: int  # tokens we sent (cost is counted per token)
    output_tokens: int  # tokens the model wrote
    model: str


class EmbeddingProvider(ABC):
    name: str
    dim: int  # how many numbers are in each embedding

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding (a list of `dim` floats) per input text, in order."""


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        """Send the rulebook (`system`) and the question plus context (`user`)."""
