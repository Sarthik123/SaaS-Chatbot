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


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a real AI provider is used but is missing settings or not built yet."""


def not_configured_message(label: str, missing: list[str]) -> str:
    """A clear, secret-free message that says exactly what to fix."""
    if missing:
        return (
            f"{label} is not configured. Set these in your .env file: "
            f"{', '.join(missing)}. (See .env.example.)"
        )
    return f"{label} is a placeholder until Phase 2, when the real connection is built."


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
