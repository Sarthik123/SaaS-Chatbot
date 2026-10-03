"""Initial schema: articles, chunks, conversations, messages, feedback, handoff tickets.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.config import get_settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _embedding_dim() -> int:
    # Tests can pass a small size through config.attributes; normal runs use EMBEDDING_DIM.
    return int(context.config.attributes.get("embedding_dim") or get_settings().embedding_dim)


def upgrade() -> None:
    # pgvector adds the "vector" column type. Safe to run if it is already enabled.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    dim = _embedding_dim()

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=False),
        # Keyword index, kept up to date by Postgres itself (a "generated column").
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True
            ),
        ),
        sa.UniqueConstraint("article_id", "chunk_index"),
    )
    op.create_index("ix_chunks_article_id", "chunks", ["article_id"])
    # GIN index: fast keyword search over tsv.
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    # HNSW index: fast "closest meaning" search over embeddings (cosine distance).
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("session_token", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("abstained", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_feedback_rating"),
    )
    op.create_index("ix_feedback_message_id", "feedback", ["message_id"])

    op.create_table(
        "handoff_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'open'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_handoff_tickets_status"),
    )
    op.create_index("ix_handoff_tickets_conversation_id", "handoff_tickets", ["conversation_id"])


def downgrade() -> None:
    # Reverse order of creation. The vector extension is left enabled on purpose.
    op.drop_table("handoff_tickets")
    op.drop_table("feedback")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("chunks")
    op.drop_table("articles")
