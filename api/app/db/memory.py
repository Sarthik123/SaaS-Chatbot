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
from typing import Any

from app.db.repository import (
    ArticleRecord,
    ChunkHit,
    ChunkRecord,
    ConversationRecord,
    FeedbackRecord,
    HandoffTicketRecord,
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
        self._feedback: list[FeedbackRecord] = []
        self._tickets: list[HandoffTicketRecord] = []
        self._next_feedback_id = 1
        self._next_ticket_id = 1

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

    # ----- feedback -----

    def add_feedback(self, message_id: str, rating: str, comment: str | None = None) -> FeedbackRecord:
        if rating not in ("up", "down"):
            raise ValueError("rating must be 'up' or 'down'")
        # Check the message exists
        with self._lock:
            found = any(
                m.id == message_id
                for msgs in self._messages.values()
                for m in msgs
            )
            if not found:
                raise ValueError(f"Unknown message_id: {message_id}")
            record = FeedbackRecord(
                id=self._next_feedback_id,
                message_id=message_id,
                rating=rating,
                comment=comment,
                created_at=datetime.now(UTC),
            )
            self._feedback.append(record)
            self._next_feedback_id += 1
            return record

    # ----- handoff tickets -----

    def create_ticket(
        self,
        conversation_id: str | None,
        name: str,
        email: str,
        message: str,
    ) -> HandoffTicketRecord:
        with self._lock:
            record = HandoffTicketRecord(
                id=self._next_ticket_id,
                conversation_id=conversation_id,
                name=name,
                email=email,
                message=message,
                status="open",
                created_at=datetime.now(UTC),
            )
            self._tickets.append(record)
            self._next_ticket_id += 1
            return record

    def list_tickets(self, status: str | None = None) -> list[HandoffTicketRecord]:
        with self._lock:
            tickets = list(self._tickets)
        if status:
            tickets = [t for t in tickets if t.status == status]
        return sorted(tickets, key=lambda t: t.created_at, reverse=True)

    # ----- admin queries -----

    def list_conversations(self, limit: int = 50) -> list[ConversationRecord]:
        with self._lock:
            convs = sorted(self._conversations.values(), key=lambda c: c.created_at, reverse=True)
        return convs[:limit]

    def list_unanswered(self, limit: int = 50) -> list[MessageRecord]:
        with self._lock:
            msgs = [
                m
                for msgs in self._messages.values()
                for m in msgs
                if m.role == "assistant" and m.abstained
            ]
        return sorted(msgs, key=lambda m: m.created_at, reverse=True)[:limit]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            all_msgs = [m for msgs in self._messages.values() for m in msgs]
        assistant_msgs = [m for m in all_msgs if m.role == "assistant"]
        abstained_count = sum(1 for m in assistant_msgs if m.abstained)
        total_msgs = len(all_msgs)
        total_assistant = len(assistant_msgs)

        # Latency
        latencies = sorted(m.latency_ms for m in assistant_msgs if m.latency_ms is not None)
        p50 = latencies[int(len(latencies) * 0.50)] if latencies else None
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else None

        # Tokens
        input_tokens = [m.input_tokens for m in assistant_msgs if m.input_tokens is not None]
        output_tokens = [m.output_tokens for m in assistant_msgs if m.output_tokens is not None]
        avg_in = sum(input_tokens) / len(input_tokens) if input_tokens else None
        avg_out = sum(output_tokens) / len(output_tokens) if output_tokens else None

        # Feedback
        with self._lock:
            fb = list(self._feedback)
        ups = sum(1 for f in fb if f.rating == "up")
        downs = sum(1 for f in fb if f.rating == "down")
        total_fb = ups + downs
        thumbs_ratio = ups / total_fb if total_fb else None

        # Tickets
        with self._lock:
            open_tickets = sum(1 for t in self._tickets if t.status == "open")

        return {
            "total_conversations": len(self._conversations),
            "total_messages": total_msgs,
            "abstain_rate": abstained_count / total_assistant if total_assistant else 0.0,
            "thumbs_up": ups,
            "thumbs_down": downs,
            "thumbs_ratio": thumbs_ratio,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "avg_input_tokens": avg_in,
            "avg_output_tokens": avg_out,
            "total_open_tickets": open_tickets,
        }
