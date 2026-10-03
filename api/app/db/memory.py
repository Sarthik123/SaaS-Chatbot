"""In-memory repository: a fake database that lives only as long as the program runs.

Used by most tests (fast, no database needed) and by the Playwright end-to-end tests. It must
behave exactly like the Postgres repository; tests/test_repository_contract.py runs the same
checks against both.
"""

import threading
from dataclasses import replace
from datetime import UTC, datetime

from app.db.repository import (
    ArticleRecord,
    ChunkRecord,
    NewChunk,
    Repository,
    validate_new_chunks,
)


class InMemoryRepository(Repository):
    def __init__(self, embedding_dim: int):
        self.embedding_dim = embedding_dim
        # FastAPI runs normal (non-async) routes in several threads, so guard shared data.
        self._lock = threading.RLock()
        self._articles: dict[int, ArticleRecord] = {}
        self._chunks: dict[int, list[ChunkRecord]] = {}  # article id -> its chunks
        self._next_article_id = 1
        self._next_chunk_id = 1

    def upsert_article(
        self,
        *,
        slug: str,
        title: str,
        source_url: str,
        body: str,
        chunks: list[NewChunk],
    ) -> ArticleRecord:
        validate_new_chunks(chunks, self.embedding_dim)
        now = datetime.now(UTC)
        with self._lock:
            existing = self._find_by_slug(slug)
            if existing is None:
                article = ArticleRecord(
                    id=self._next_article_id,
                    title=title,
                    slug=slug,
                    source_url=source_url,
                    body=body,
                    created_at=now,
                    updated_at=now,
                )
                self._next_article_id += 1
            else:
                article = replace(
                    existing, title=title, source_url=source_url, body=body, updated_at=now
                )
            self._articles[article.id] = article
            stored = []
            for chunk in sorted(chunks, key=lambda c: c.chunk_index):
                stored.append(
                    ChunkRecord(
                        id=self._next_chunk_id,
                        article_id=article.id,
                        chunk_index=chunk.chunk_index,
                        heading=chunk.heading,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        embedding=list(chunk.embedding),
                    )
                )
                self._next_chunk_id += 1
            self._chunks[article.id] = stored
            return article

    def get_article(self, article_id: int) -> ArticleRecord | None:
        with self._lock:
            return self._articles.get(article_id)

    def get_article_by_slug(self, slug: str) -> ArticleRecord | None:
        with self._lock:
            return self._find_by_slug(slug)

    def list_articles(self) -> list[ArticleRecord]:
        with self._lock:
            return sorted(self._articles.values(), key=lambda a: a.slug)

    def delete_article(self, article_id: int) -> bool:
        with self._lock:
            if article_id not in self._articles:
                return False
            del self._articles[article_id]
            self._chunks.pop(article_id, None)
            return True

    def list_chunks(self, article_id: int) -> list[ChunkRecord]:
        with self._lock:
            return list(self._chunks.get(article_id, []))

    def count_articles(self) -> int:
        with self._lock:
            return len(self._articles)

    def count_chunks(self) -> int:
        with self._lock:
            return sum(len(chunks) for chunks in self._chunks.values())

    def _find_by_slug(self, slug: str) -> ArticleRecord | None:
        for article in self._articles.values():
            if article.slug == slug:
                return article
        return None
