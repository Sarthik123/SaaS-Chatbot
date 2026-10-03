"""The storage "contract": what the rest of the app may ask the database to do.

Business logic (chunking, retrieval, answering, admin) only talks to this interface. There are
two implementations that must behave the same way:

  * InMemoryRepository  (api/app/db/memory.py)    used by most tests: instant, no database
  * PostgresRepository  (api/app/db/postgres.py)  used when DATABASE_URL is set

Why: tests that do not need a real database run in milliseconds and anywhere, and a few
"integration" tests prove the Postgres version behaves exactly like the fake.
"""

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
