"""Fake AI providers: free, instant, offline and fully predictable.

They exist so every automated test can run with no internet and no paid calls.
They are NOT intelligent. Numbers produced with them say nothing about answer quality.
"""

import hashlib
import json
import math
import re

from app.providers.base import EmbeddingProvider, LLMProvider, LLMResult

_WORD = re.compile(r"[a-z0-9]+")
# Finds <context id='abc'> tags in the prompt sent to the language model.
_CONTEXT_ID = re.compile(r"""<context\s+id=['"]([^'"]+)['"]\s*>""")


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embeddings built from the words in the text.

    Same text -> same vector, always (we use sha256, not Python's randomised hash()).
    Texts that share words get a higher cosine similarity than texts that do not.
    """

    name = "fake"

    def __init__(self, dim: int = 384):
        if dim < 8:
            raise ValueError("dim must be at least 8")
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        words = _WORD.findall(text.lower()) or ["<empty>"]  # never produce an all-zero vector
        vector = [0.0] * self.dim
        for word in words:
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dim
            vector[slot] += 1.0
        length = math.sqrt(sum(value * value for value in vector))
        return [value / length for value in vector]  # length 1, so dot product = cosine


def _rough_token_count(text: str) -> int:
    """Very rough token estimate (word count). Good enough for a fake."""
    return len(text.split())


class FakeLLMProvider(LLMProvider):
    """A pretend language model.

    By default it returns valid JSON that cites the FIRST <context id='...'> it was given,
    or can_answer=false when there is no context. Tests can also hand it `scripted_outputs`
    (for example broken JSON) and read `.calls` to check whether it was called at all.
    """

    name = "fake"
    model = "fake-llm"

    def __init__(self, scripted_outputs: list[str] | None = None):
        self._scripted = list(scripted_outputs or [])
        self.calls: list[dict[str, str]] = []

    def generate(self, system: str, user: str, max_output_tokens: int = 400) -> LLMResult:
        self.calls.append({"system": system, "user": user})
        text = self._scripted.pop(0) if self._scripted else self._default_reply(user)
        return LLMResult(
            text=text,
            input_tokens=_rough_token_count(system) + _rough_token_count(user),
            output_tokens=_rough_token_count(text),
            model=self.model,
        )

    @staticmethod
    def _default_reply(user_prompt: str) -> str:
        chunk_ids = _CONTEXT_ID.findall(user_prompt)
        if not chunk_ids:
            reply = {"can_answer": False, "answer": "", "used_chunk_ids": []}
        else:
            reply = {
                "can_answer": True,
                # A fixed sentence on purpose: the fake never copies text from the context.
                "answer": f"FAKE ANSWER built from context {chunk_ids[0]}.",
                "used_chunk_ids": [chunk_ids[0]],
            }
        return json.dumps(reply)
