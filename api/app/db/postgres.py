"""Postgres repository: the real database (Neon in production).

Behaves exactly like InMemoryRepository; see tests/test_repository_contract.py.
"""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, desc, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import Article, Chunk, Conversation, Message
from app.db.repository import (
    ArticleRecord,
    ChunkHit,
    ChunkRecord,
    ConversationRecord,
    MessageRecord,
    NewChunk,
    Repository,
    normalize_uuid,
    validate_new_chunks,
    validate_query_embedding,
)
from app.db.textsearch import query_words, web_query


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


def _to_conversation(row: Conversation) -> ConversationRecord:
    return ConversationRecord(id=row.id, session_token=row.session_token, created_at=row.created_at)


def _to_message(row: Message) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        citations=row.citations,
        abstained=row.abstained,
        retrieved_chunk_ids=row.retrieved_chunk_ids,
        latency_ms=row.latency_ms,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        model=row.model,
        created_at=row.created_at,
    )


def _to_hit(row) -> ChunkHit:
    return ChunkHit(
        chunk_id=row.id,
        article_id=row.article_id,
        chunk_index=row.chunk_index,
        heading=row.heading,
        text=row.text,
        token_count=row.token_count,
        article_title=row.title,
        article_slug=row.slug,
        source_url=row.source_url,
        similarity=float(row.similarity),
        keyword_score=float(getattr(row, "keyword_score", 0.0) or 0.0),
    )


class PostgresRepository(Repository):
    def __init__(self, engine: Engine, embedding_dim: int):
        self.embedding_dim = embedding_dim
        self._engine = engine
        # expire_on_commit=False: rows stay readable after the transaction ends.
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    # ----- articles and chunks -----

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

    # ----- searching -----

    @staticmethod
    def _hit_columns(distance):
        return [
            Chunk.id,
            Chunk.article_id,
            Chunk.chunk_index,
            Chunk.heading,
            Chunk.text,
            Chunk.token_count,
            Article.title,
            Article.slug,
            Article.source_url,
            (1 - distance).label("similarity"),
        ]

    def search_vector(self, embedding: list[float], limit: int) -> list[ChunkHit]:
        validate_query_embedding(embedding, self.embedding_dim)
        # <=> is pgvector's "cosine distance" (0 = identical). similarity = 1 - distance.
        distance = Chunk.embedding.cosine_distance(embedding)
        statement = (
            select(*self._hit_columns(distance))
            .join(Article, Article.id == Chunk.article_id)
            .order_by(distance, Chunk.id)
            .limit(limit)
        )
        with self._sessions() as session:
            return [_to_hit(row) for row in session.execute(statement)]

    def search_keyword(self, query: str, embedding: list[float], limit: int) -> list[ChunkHit]:
        validate_query_embedding(embedding, self.embedding_dim)
        words = query_words(query)
        if not words:
            return []
        # websearch_to_tsquery understands "a or b or c"; it stems the words and drops stop words.
        ts_query = func.websearch_to_tsquery("english", web_query(words))
        keyword_score = func.ts_rank(Chunk.tsv, ts_query).label("keyword_score")
        distance = Chunk.embedding.cosine_distance(embedding)
        statement = (
            select(*self._hit_columns(distance), keyword_score)
            .join(Article, Article.id == Chunk.article_id)
            .where(Chunk.tsv.op("@@")(ts_query))
            .order_by(desc(keyword_score), Chunk.id)
            .limit(limit)
        )
        with self._sessions() as session:
            return [_to_hit(row) for row in session.execute(statement)]

    # ----- conversations and messages -----

    def create_conversation(self) -> ConversationRecord:
        with self._sessions.begin() as session:
            row = Conversation(
                id=str(uuid.uuid4()),
                session_token=secrets.token_urlsafe(16),
                created_at=datetime.now(UTC),
            )
            session.add(row)
            session.flush()
            return _to_conversation(row)

    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        key = normalize_uuid(conversation_id)
        if key is None:
            return None
        with self._sessions() as session:
            row = session.get(Conversation, key)
            return _to_conversation(row) if row else None

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
        if role not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        key = normalize_uuid(conversation_id)
        if key is None:
            raise ValueError("Unknown conversation.")
        try:
            with self._sessions.begin() as session:
                row = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=key,
                    role=role,
                    content=content,
                    citations=citations,
                    abstained=abstained,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=model,
                    created_at=datetime.now(UTC),
                )
                session.add(row)
                session.flush()
                return _to_message(row)
        except IntegrityError as error:  # the foreign key failed: no such conversation
            raise ValueError("Unknown conversation.") from error

    def list_messages(self, conversation_id: str, limit: int | None = None) -> list[MessageRecord]:
        key = normalize_uuid(conversation_id)
        if key is None:
            return []
        statement = select(Message).where(Message.conversation_id == key)
        with self._sessions() as session:
            if limit:
                rows = session.scalars(
                    statement.order_by(desc(Message.created_at), desc(Message.id)).limit(limit)
                ).all()
                rows = list(reversed(rows))
            else:
                rows = session.scalars(statement.order_by(Message.created_at, Message.id)).all()
            return [_to_message(row) for row in rows]
