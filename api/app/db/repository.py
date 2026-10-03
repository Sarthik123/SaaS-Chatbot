"""The storage "contract": what the rest of the app may ask the database to do.

Business logic (chunking, retrieval, answering, admin) only talks to this interface. There are
two implementations that must behave the same way:

  * InMemoryRepository  (api/app/db/memory.py)    used by most tests: instant, no database
  * PostgresRepository  (api/app/db/postgres.py)  used when DATABASE_URL is set

Why: tests that do not need a real database run in milliseconds and anywhere, and a few
"integration" tests prove the Postgres version behaves exactly like the fake.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleRecord:
    id: int
    title: str
    slug: str
    source_url: str
    body: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NewChunk:
    """A chunk ready to be stored (it does not have a database id yet)."""

    chunk_index: int
    heading: str
    text: str
    token_count: int
    embedding: list[float]


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    article_id: int
    chunk_index: int
    heading: str
    text: str
    token_count: int
    embedding: list[float]


@dataclass(frozen=True)
class ChunkHit:
    """A chunk found by a search, with the article it belongs to and how well it matched."""

    chunk_id: int
    article_id: int
    chunk_index: int
    heading: str
    text: str
    token_count: int
    article_title: str
    article_slug: str
    source_url: str
    # Cosine similarity between the question and this chunk: 1.0 = same meaning, near 0 = unrelated.
    similarity: float
    # Keyword-match strength (0.0 for a hit that came from the meaning search).
    keyword_score: float = 0.0


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    session_token: str
    created_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: str
    conversation_id: str
    role: str  # 'user' or 'assistant'
    content: str
    citations: list[dict] | None
    abstained: bool
    retrieved_chunk_ids: list[int] | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    model: str | None
    created_at: datetime


def validate_new_chunks(chunks: list[NewChunk], embedding_dim: int) -> None:
    """Shared safety checks so both repositories reject bad input in the same way."""
    seen: set[int] = set()
    for chunk in chunks:
        if len(chunk.embedding) != embedding_dim:
            raise ValueError(
                f"Embedding has {len(chunk.embedding)} numbers but EMBEDDING_DIM is "
                f"{embedding_dim}. The embedding model and EMBEDDING_DIM must match."
            )
        if chunk.chunk_index in seen:
            raise ValueError(f"Duplicate chunk_index {chunk.chunk_index} in one article.")
        seen.add(chunk.chunk_index)


def validate_query_embedding(embedding: list[float], embedding_dim: int) -> None:
    if len(embedding) != embedding_dim:
        raise ValueError(
            f"Question embedding has {len(embedding)} numbers but EMBEDDING_DIM is "
            f"{embedding_dim}. The embedding model and EMBEDDING_DIM must match."
        )


def normalize_uuid(value: str | None) -> str | None:
    """A clean lower-case UUID string, or None when the value is not a valid UUID."""
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class Repository(ABC):
    embedding_dim: int  # how many numbers are in each embedding

    # ----- articles and their chunks -----

    @abstractmethod
    def upsert_article(
        self,
        *,
        slug: str,
        title: str,
        source_url: str,
        body: str,
        chunks: list[NewChunk],
    ) -> ArticleRecord:
        """Create the article, or update it if the slug already exists.

        All of the article's old chunks are replaced by `chunks` in one step, so running an
        import twice never creates duplicates. Raises ValueError if an embedding has the wrong size.
        """

    @abstractmethod
    def get_article(self, article_id: int) -> ArticleRecord | None: ...

    @abstractmethod
    def get_article_by_slug(self, slug: str) -> ArticleRecord | None: ...

    @abstractmethod
    def list_articles(self) -> list[ArticleRecord]:
        """All articles, ordered by slug."""

    @abstractmethod
    def delete_article(self, article_id: int) -> bool:
        """Delete the article and its chunks. Returns False if there was no such article."""

    @abstractmethod
    def list_chunks(self, article_id: int) -> list[ChunkRecord]:
        """The article's chunks, ordered by chunk_index."""

    @abstractmethod
    def count_articles(self) -> int: ...

    @abstractmethod
    def count_chunks(self) -> int: ...

    # ----- searching -----

    @abstractmethod
    def search_vector(self, embedding: list[float], limit: int) -> list[ChunkHit]:
        """The `limit` chunks whose meaning is closest to `embedding`, best first."""

    @abstractmethod
    def search_keyword(self, query: str, embedding: list[float], limit: int) -> list[ChunkHit]:
        """The `limit` chunks that contain the words of `query`, best match first.

        Words are matched after stemming and common words are ignored. A chunk needs only ONE
        of the words to match (a question never repeats an article word for word). `embedding`
        is the question's embedding; it is only used to fill in each hit's `similarity`.
        """

    # ----- conversations and messages -----

    @abstractmethod
    def create_conversation(self) -> ConversationRecord: ...

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        """None for an unknown id and also for text that is not a valid id."""

    @abstractmethod
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        citations: list[dict] | None = None,
        abstained: bool = False,
        retrieved_chunk_ids: list[int] | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
    ) -> MessageRecord:
        """Raises ValueError for an unknown conversation or a role other than user/assistant."""

    @abstractmethod
    def list_messages(self, conversation_id: str, limit: int | None = None) -> list[MessageRecord]:
        """Messages oldest first. With `limit`, only the most recent `limit` messages."""
