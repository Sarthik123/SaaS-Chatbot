"""In-memory repository: a fake database that lives only as long as the program runs.

Used by most tests (fast, no database needed) and by the Playwright end-to-end tests. It must
behave exactly like the Postgres repository; tests/test_repository_contract.py runs the same
checks against both.
"""

import math
import secrets
import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime

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
from app.db.textsearch import index_terms, keyword_score, query_words


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class InMemoryRepository(Repository):
    def __init__(self, embedding_dim: int):
        self.embedding_dim = embedding_dim
        # FastAPI runs normal (non-async) routes in several threads, so guard shared data.
        self._lock = threading.RLock()
        self._articles: dict[int, ArticleRecord] = {}
        self._chunks: dict[int, list[ChunkRecord]] = {}  # article id -> its chunks
        self._next_article_id = 1
        self._next_chunk_id = 1
        self._conversations: dict[str, ConversationRecord] = {}
        self._messages: dict[str, list[MessageRecord]] = {}  # conversation id -> messages

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

    # ----- searching -----

    def _hit(self, chunk: ChunkRecord, similarity: float, keyword: float = 0.0) -> ChunkHit:
        article = self._articles[chunk.article_id]
        return ChunkHit(
            chunk_id=chunk.id,
            article_id=chunk.article_id,
            chunk_index=chunk.chunk_index,
            heading=chunk.heading,
            text=chunk.text,
            token_count=chunk.token_count,
            article_title=article.title,
            article_slug=article.slug,
            source_url=article.source_url,
            similarity=similarity,
            keyword_score=keyword,
        )

    def _all_chunks(self) -> list[ChunkRecord]:
        return [chunk for chunks in self._chunks.values() for chunk in chunks]

    def search_vector(self, embedding: list[float], limit: int) -> list[ChunkHit]:
        validate_query_embedding(embedding, self.embedding_dim)
        with self._lock:
            scored = [(_cosine(embedding, c.embedding), c) for c in self._all_chunks()]
            scored.sort(key=lambda pair: (-pair[0], pair[1].id))
            return [self._hit(chunk, similarity) for similarity, chunk in scored[:limit]]

    def search_keyword(self, query: str, embedding: list[float], limit: int) -> list[ChunkHit]:
        validate_query_embedding(embedding, self.embedding_dim)
        words = query_words(query)
        if not words:
            return []
        with self._lock:
            matches = []
            for chunk in self._all_chunks():
                terms = index_terms(f"{chunk.heading}\n{chunk.text}")
                score = keyword_score(terms, words)
                if score > 0:
                    matches.append((score, chunk))
            matches.sort(key=lambda pair: (-pair[0], pair[1].id))
            return [
                self._hit(chunk, _cosine(embedding, chunk.embedding), score)
                for score, chunk in matches[:limit]
            ]

    # ----- conversations and messages -----

    def create_conversation(self) -> ConversationRecord:
        with self._lock:
            conversation = ConversationRecord(
                id=str(uuid.uuid4()),
                session_token=secrets.token_urlsafe(16),
                created_at=datetime.now(UTC),
            )
            self._conversations[conversation.id] = conversation
            self._messages[conversation.id] = []
            return conversation

    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        key = normalize_uuid(conversation_id)
        with self._lock:
            return self._conversations.get(key) if key else None

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
        with self._lock:
            if key is None or key not in self._conversations:
                raise ValueError("Unknown conversation.")
            message = MessageRecord(
                id=str(uuid.uuid4()),
                conversation_id=key,
                role=role,
                content=content,
                citations=[dict(c) for c in citations] if citations is not None else None,
                abstained=abstained,
                retrieved_chunk_ids=list(retrieved_chunk_ids)
                if retrieved_chunk_ids is not None
                else None,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model,
                created_at=datetime.now(UTC),
            )
            self._messages[key].append(message)
            return message

    def list_messages(self, conversation_id: str, limit: int | None = None) -> list[MessageRecord]:
        key = normalize_uuid(conversation_id)
        with self._lock:
            messages = list(self._messages.get(key, [])) if key else []
        return messages[-limit:] if limit else messages
