"""The database tables, described as Python classes (SQLAlchemy "models").

The real tables are created by the Alembic migration in api/migrations/versions/. These classes
describe the same tables so the Postgres repository can read and write them.

Tables (see AGENTS.md "Data model"):
  articles       one row per help article
  chunks         small pieces of an article, with the embedding (meaning-numbers) and tsvector
                 (keyword index) used for search
  conversations  one row per chat session
  messages       every question and answer, with speed, tokens, citations
  feedback       thumbs up / thumbs down on an answer
  handoff_tickets  "talk to a human" requests
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _new_id() -> str:
    # Conversation and message ids are random UUIDs so nobody can guess another person's id.
    return str(uuid.uuid4())


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("article_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    # The size of the vector (EMBEDDING_DIM) is fixed by the migration; the model only needs
    # to know "this column holds a vector".
    embedding: Mapped[list[float]] = mapped_column(Vector())
    # Keyword index, computed by Postgres itself from heading + text (never set by our code).
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_new_id)
    session_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating IN ('up', 'down')", name="ck_feedback_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[str] = mapped_column(String(8))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HandoffTicket(Base):
    __tablename__ = "handoff_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_handoff_tickets_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SET NULL (not CASCADE): deleting a chat does not silently delete a help request that a
    # person explicitly sent to the support team. See docs/DECISIONS.md.
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
