"""Postgres repository: the real database (Neon in production).

Behaves exactly like InMemoryRepository; see tests/test_repository_contract.py.
"""

from datetime import UTC, datetime

from sqlalchemy import Engine, delete, func, insert, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Article, Chunk
from app.db.repository import (
    ArticleRecord,
    ChunkRecord,
    NewChunk,
    Repository,
    validate_new_chunks,
)


def _to_article(row: Article) -> ArticleRecord:
    return ArticleRecord(
        id=row.id,
        title=row.title,
        slug=row.slug,
        source_url=row.source_url,
        body=row.body,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_chunk(row: Chunk) -> ChunkRecord:
    return ChunkRecord(
        id=row.id,
        article_id=row.article_id,
        chunk_index=row.chunk_index,
        heading=row.heading,
        text=row.text,
        token_count=row.token_count,
        embedding=[float(value) for value in row.embedding],
    )


class PostgresRepository(Repository):
    def __init__(self, engine: Engine, embedding_dim: int):
        self.embedding_dim = embedding_dim
        self._engine = engine
        # expire_on_commit=False: rows stay readable after the transaction ends.
        self._sessions = sessionmaker(engine, expire_on_commit=False)

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
        # session.begin() = one transaction: either everything below is saved, or nothing is.
        with self._sessions.begin() as session:
            article = session.scalar(select(Article).where(Article.slug == slug))
            if article is None:
                article = Article(
                    slug=slug,
                    title=title,
                    source_url=source_url,
                    body=body,
                    created_at=now,
                    updated_at=now,
                )
                session.add(article)
                session.flush()  # gives the new article its id
            else:
                article.title = title
                article.source_url = source_url
                article.body = body
                article.updated_at = now
                session.execute(delete(Chunk).where(Chunk.article_id == article.id))
            if chunks:
                session.execute(
                    insert(Chunk),
                    [
                        {
                            "article_id": article.id,
                            "chunk_index": chunk.chunk_index,
                            "heading": chunk.heading,
                            "text": chunk.text,
                            "token_count": chunk.token_count,
                            "embedding": list(chunk.embedding),
                        }
                        for chunk in chunks
                    ],
                )
            return _to_article(article)

    def get_article(self, article_id: int) -> ArticleRecord | None:
        with self._sessions() as session:
            row = session.get(Article, article_id)
            return _to_article(row) if row else None

    def get_article_by_slug(self, slug: str) -> ArticleRecord | None:
        with self._sessions() as session:
            row = session.scalar(select(Article).where(Article.slug == slug))
            return _to_article(row) if row else None

    def list_articles(self) -> list[ArticleRecord]:
        with self._sessions() as session:
            rows = session.scalars(select(Article).order_by(Article.slug)).all()
            return [_to_article(row) for row in rows]

    def delete_article(self, article_id: int) -> bool:
        with self._sessions.begin() as session:
            # The database deletes the article's chunks too (ON DELETE CASCADE).
            result = session.execute(delete(Article).where(Article.id == article_id))
            return result.rowcount > 0

    def list_chunks(self, article_id: int) -> list[ChunkRecord]:
        with self._sessions() as session:
            rows = session.scalars(
                select(Chunk).where(Chunk.article_id == article_id).order_by(Chunk.chunk_index)
            ).all()
            return [_to_chunk(row) for row in rows]

    def count_articles(self) -> int:
        with self._sessions() as session:
            return session.scalar(select(func.count()).select_from(Article)) or 0

    def count_chunks(self) -> int:
        with self._sessions() as session:
            return session.scalar(select(func.count()).select_from(Chunk)) or 0
