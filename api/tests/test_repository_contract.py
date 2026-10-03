"""The same checks run against the in-memory fake AND the real Postgres repository.

If a test passes for one and fails for the other, the fake is lying, and every test that
relies on the fake would be meaningless. The Postgres runs are marked "integration" and are
skipped unless DATABASE_URL was set when pytest started.
"""

import time
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.memory import InMemoryRepository
from app.db.postgres import PostgresRepository
from app.db.repository import NewChunk
from app.db.session import make_engine
from tests.conftest import REAL_DATABASE_URL

# (feedback, tickets and stats contract tests are later in this file)

DIM = 16
API_DIR = Path(__file__).resolve().parents[1]


def vector(seed: float) -> list[float]:
    return [seed + i / 100 for i in range(DIM)]


def chunk(index: int, seed: float = 0.1, **overrides) -> NewChunk:
    values = {
        "chunk_index": index,
        "heading": f"Heading {index}",
        "text": f"Text of chunk {index} about invoices.",
        "token_count": 8,
        "embedding": vector(seed + index),
    }
    values.update(overrides)
    return NewChunk(**values)


def save(repo, slug="late-fees", title="Late fees", chunks=None, body="# Late fees"):
    return repo.upsert_article(
        slug=slug,
        title=title,
        source_url=f"https://help.example/{slug}",
        body=body,
        chunks=[chunk(0), chunk(1)] if chunks is None else chunks,
    )


@pytest.fixture
def postgres_repo():
    if not REAL_DATABASE_URL:
        pytest.skip("DATABASE_URL was not set when pytest started")
    # A private schema, so the test never touches real tables.
    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin_engine = make_engine(REAL_DATABASE_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = make_engine(REAL_DATABASE_URL, options=f"-c search_path={schema},public")
    try:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["embedding_dim"] = DIM
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield PostgresRepository(engine, DIM)
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.integration)])
def repo(request):
    if request.param == "memory":
        return InMemoryRepository(DIM)
    return request.getfixturevalue("postgres_repo")


def test_a_new_article_is_stored_with_its_chunks(repo):
    article = save(repo)
    assert article.id > 0
    assert (article.slug, article.title) == ("late-fees", "Late fees")
    assert repo.count_articles() == 1
    assert repo.count_chunks() == 2
    assert repo.get_article(article.id) == article
    assert repo.get_article_by_slug("late-fees") == article


def test_saving_the_same_slug_again_updates_instead_of_duplicating(repo):
    first = save(repo)
    time.sleep(0.01)
    second = save(repo, title="Late fees (new)", chunks=[chunk(0, seed=0.5)], body="# New body")
    assert second.id == first.id
    assert second.title == "Late fees (new)"
    assert second.body == "# New body"
    assert second.created_at == first.created_at
    assert second.updated_at > first.updated_at
    assert repo.count_articles() == 1
    assert repo.count_chunks() == 1  # the old two chunks were replaced
    assert repo.get_article(first.id).title == "Late fees (new)"


def test_unknown_articles_come_back_as_none(repo):
    assert repo.get_article(999) is None
    assert repo.get_article_by_slug("nope") is None


def test_articles_are_listed_in_slug_order(repo):
    for slug in ["zebra", "apple", "mango"]:
        save(repo, slug=slug, title=slug, chunks=[chunk(0)])
    assert [a.slug for a in repo.list_articles()] == ["apple", "mango", "zebra"]


def test_deleting_an_article_deletes_its_chunks(repo):
    keep = save(repo, slug="keep", chunks=[chunk(0)])
    gone = save(repo, slug="gone", chunks=[chunk(0), chunk(1)])
    assert repo.delete_article(gone.id) is True
    assert repo.delete_article(gone.id) is False  # already gone
    assert repo.get_article(gone.id) is None
    assert repo.list_chunks(gone.id) == []
    assert repo.count_articles() == 1
    assert repo.count_chunks() == 1
    assert repo.get_article(keep.id) is not None


def test_chunks_come_back_in_chunk_index_order_with_their_data(repo):
    article = save(repo, chunks=[chunk(2), chunk(0), chunk(1)])
    stored = repo.list_chunks(article.id)
    assert [c.chunk_index for c in stored] == [0, 1, 2]
    assert stored[0].heading == "Heading 0"
    assert stored[0].text == "Text of chunk 0 about invoices."
    assert stored[0].token_count == 8
    assert all(c.article_id == article.id for c in stored)
    assert all(c.id > 0 for c in stored)


def test_embeddings_survive_a_round_trip(repo):
    article = save(repo, chunks=[chunk(0, seed=0.25)])
    (stored,) = repo.list_chunks(article.id)
    assert stored.embedding == pytest.approx(vector(0.25), abs=1e-6)


def test_an_article_can_be_saved_with_no_chunks(repo):
    article = save(repo, chunks=[])
    assert repo.list_chunks(article.id) == []
    assert repo.count_chunks() == 0


def test_an_embedding_of_the_wrong_size_is_rejected_and_nothing_is_saved(repo):
    bad = chunk(0, embedding=[0.1, 0.2])
    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        save(repo, chunks=[bad])
    assert repo.count_articles() == 0
    assert repo.count_chunks() == 0


def test_a_repeated_chunk_index_is_rejected(repo):
    with pytest.raises(ValueError, match="Duplicate chunk_index"):
        save(repo, chunks=[chunk(0), chunk(0)])
    assert repo.count_articles() == 0


# ---------- vector and keyword search ----------


def test_search_vector_returns_closest_chunk_first(repo):
    save(repo, slug="a", chunks=[chunk(0, seed=0.1)])
    save(repo, slug="b", chunks=[chunk(0, seed=0.5)])
    # Query with a vector close to seed=0.5
    query = vector(0.5)
    hits = repo.search_vector(query, limit=2)
    assert len(hits) == 2
    assert hits[0].similarity >= hits[1].similarity


def test_search_vector_respects_limit(repo):
    for i in range(5):
        save(repo, slug=f"art-{i}", chunks=[chunk(0, seed=i * 0.1)])
    hits = repo.search_vector(vector(0.3), limit=2)
    assert len(hits) <= 2


def test_search_vector_empty_repo_returns_empty_list(repo):
    assert repo.search_vector(vector(0.1), limit=8) == []


def test_search_keyword_finds_matching_chunk(repo):
    save(repo, slug="invoices", chunks=[chunk(0, text="monthly invoice export csv billing")])
    save(repo, slug="passwords", chunks=[chunk(0, text="reset password settings account")])
    query_embedding = vector(0.1)
    hits = repo.search_keyword("invoice billing", query_embedding, limit=8)
    slugs = [h.article_slug for h in hits]
    assert "invoices" in slugs


def test_search_keyword_returns_empty_for_stopwords_only(repo):
    save(repo, slug="art", chunks=[chunk(0, text="how the system works")])
    hits = repo.search_keyword("the how", vector(0.1), limit=8)
    # "the" and "how" are stopwords; zero useful words means no hits.
    assert hits == []


def test_search_vector_rejects_wrong_dimension(repo):
    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        repo.search_vector([0.1, 0.2], limit=5)  # DIM is 16, not 2


# ---------- conversations and messages ----------


def test_create_conversation_returns_a_record_with_an_id(repo):
    conv = repo.create_conversation()
    assert conv.id
    assert conv.session_token


def test_get_conversation_finds_an_existing_conversation(repo):
    conv = repo.create_conversation()
    assert repo.get_conversation(conv.id) == conv


def test_get_conversation_returns_none_for_unknown_id(repo):
    assert repo.get_conversation("00000000-0000-0000-0000-000000000000") is None


def test_get_conversation_returns_none_for_garbage_id(repo):
    assert repo.get_conversation("not-a-uuid") is None


def test_add_message_stores_and_retrieves_content(repo):
    conv = repo.create_conversation()
    msg = repo.add_message(conv.id, "user", "hello world")
    assert msg.id
    assert msg.role == "user"
    assert msg.content == "hello world"


def test_list_messages_returns_messages_in_insertion_order(repo):
    conv = repo.create_conversation()
    repo.add_message(conv.id, "user", "first")
    repo.add_message(conv.id, "assistant", "second")
    repo.add_message(conv.id, "user", "third")
    messages = repo.list_messages(conv.id)
    assert [m.content for m in messages] == ["first", "second", "third"]


def test_list_messages_limit_returns_only_the_most_recent(repo):
    conv = repo.create_conversation()
    for i in range(5):
        repo.add_message(conv.id, "user", f"msg {i}")
    last_two = repo.list_messages(conv.id, limit=2)
    assert len(last_two) == 2
    assert last_two[0].content == "msg 3"
    assert last_two[1].content == "msg 4"


def test_list_messages_unknown_conversation_returns_empty_list(repo):
    assert repo.list_messages("00000000-0000-0000-0000-000000000000") == []


def test_add_message_rejects_invalid_role(repo):
    conv = repo.create_conversation()
    with pytest.raises(ValueError, match="role"):
        repo.add_message(conv.id, "moderator", "hi")


def test_add_message_stores_optional_metadata(repo):
    conv = repo.create_conversation()
    msg = repo.add_message(
        conv.id,
        "assistant",
        "Here is the answer.",
        citations=[{"article_id": 1, "title": "Help", "url": "https://x", "chunk_id": 2, "quote": "text"}],
        abstained=False,
        retrieved_chunk_ids=[2, 3],
        latency_ms=123,
        input_tokens=50,
        output_tokens=20,
        model="fake-llm",
    )
    assert msg.latency_ms == 123
    assert msg.input_tokens == 50
    assert msg.output_tokens == 20
    assert msg.model == "fake-llm"
    assert msg.retrieved_chunk_ids == [2, 3]
    assert msg.abstained is False
    assert msg.citations is not None and len(msg.citations) == 1


# ---------- feedback ----------


def test_add_feedback_returns_a_record(repo):
    conv = repo.create_conversation()
    msg = repo.add_message(conv.id, "assistant", "answer")
    fb = repo.add_feedback(msg.id, "up")
    assert fb.id > 0
    assert fb.rating == "up"
    assert fb.message_id == msg.id


def test_add_feedback_down_with_comment(repo):
    conv = repo.create_conversation()
    msg = repo.add_message(conv.id, "assistant", "answer")
    fb = repo.add_feedback(msg.id, "down", comment="not helpful")
    assert fb.rating == "down"
    assert fb.comment == "not helpful"


def test_add_feedback_rejects_unknown_message(repo):
    with pytest.raises(ValueError):
        repo.add_feedback("00000000-0000-0000-0000-000000000000", "up")


def test_add_feedback_rejects_invalid_rating(repo):
    conv = repo.create_conversation()
    msg = repo.add_message(conv.id, "assistant", "answer")
    with pytest.raises(ValueError, match="rating"):
        repo.add_feedback(msg.id, "meh")


# ---------- handoff tickets ----------


def test_create_ticket_returns_a_record(repo):
    ticket = repo.create_ticket(None, "Alice", "alice@example.com", "I need help.")
    assert ticket.id > 0
    assert ticket.status == "open"
    assert ticket.name == "Alice"


def test_list_tickets_newest_first(repo):
    import time
    repo.create_ticket(None, "A", "a@x.com", "first")
    time.sleep(0.01)
    repo.create_ticket(None, "B", "b@x.com", "second")
    tickets = repo.list_tickets()
    assert tickets[0].name == "B"
    assert tickets[1].name == "A"


def test_list_tickets_filtered_by_status(repo):
    repo.create_ticket(None, "A", "a@x.com", "msg")
    tickets_open = repo.list_tickets(status="open")
    tickets_closed = repo.list_tickets(status="closed")
    assert len(tickets_open) == 1
    assert len(tickets_closed) == 0


def test_list_tickets_all_when_no_filter(repo):
    repo.create_ticket(None, "A", "a@x.com", "msg")
    repo.create_ticket(None, "B", "b@x.com", "msg")
    assert len(repo.list_tickets()) == 2


# ---------- admin queries ----------


def test_list_conversations_newest_first(repo):
    import time
    repo.create_conversation()
    time.sleep(0.01)
    second = repo.create_conversation()
    convs = repo.list_conversations(limit=10)
    assert convs[0].id == second.id


def test_list_unanswered_returns_abstained_assistant_messages(repo):
    conv = repo.create_conversation()
    repo.add_message(conv.id, "user", "question")
    repo.add_message(conv.id, "assistant", "fallback", abstained=True)
    unanswered = repo.list_unanswered(limit=10)
    assert len(unanswered) == 1
    assert unanswered[0].abstained is True


def test_list_unanswered_excludes_non_abstained(repo):
    conv = repo.create_conversation()
    repo.add_message(conv.id, "user", "question")
    repo.add_message(conv.id, "assistant", "answer", abstained=False)
    assert repo.list_unanswered(limit=10) == []


def test_get_stats_returns_zeros_for_empty_repo(repo):
    stats = repo.get_stats()
    assert stats["total_conversations"] == 0
    assert stats["total_messages"] == 0
    assert stats["abstain_rate"] == 0.0
    assert stats["thumbs_up"] == 0
    assert stats["total_open_tickets"] == 0


def test_get_stats_counts_correctly(repo):
    conv = repo.create_conversation()
    repo.add_message(conv.id, "user", "q1")
    msg = repo.add_message(conv.id, "assistant", "a1", abstained=False, latency_ms=200)
    repo.add_feedback(msg.id, "up")
    stats = repo.get_stats()
    assert stats["total_conversations"] == 1
    assert stats["total_messages"] == 2
    assert stats["thumbs_up"] == 1
    assert stats["thumbs_ratio"] == 1.0


# ---------- Postgres-only checks (need a real database) ----------


@pytest.mark.integration
def test_postgres_fills_the_keyword_index_by_itself(postgres_repo):
    article = save(postgres_repo, chunks=[chunk(0, text="Late fees are capped at 25 percent.")])
    with postgres_repo._engine.connect() as connection:
        matches = connection.execute(
            text(
                "SELECT count(*) FROM chunks "
                "WHERE article_id = :id AND tsv @@ plainto_tsquery('english', 'capped fee')"
            ),
            {"id": article.id},
        ).scalar_one()
        no_match = connection.execute(
            text("SELECT count(*) FROM chunks WHERE tsv @@ plainto_tsquery('english', 'payroll')")
        ).scalar_one()
    assert matches == 1
    assert no_match == 0


@pytest.mark.integration
def test_postgres_has_the_search_indexes(postgres_repo):
    with postgres_repo._engine.connect() as connection:
        rows = connection.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chunks'")
        ).all()
    definitions = {name: definition for name, definition in rows}
    assert "USING hnsw" in definitions["ix_chunks_embedding_hnsw"]
    assert "vector_cosine_ops" in definitions["ix_chunks_embedding_hnsw"]
    assert "USING gin" in definitions["ix_chunks_tsv"]


@pytest.mark.integration
def test_postgres_has_every_table_from_the_data_model(postgres_repo):
    with postgres_repo._engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            )
        }
    assert {
        "articles",
        "chunks",
        "conversations",
        "messages",
        "feedback",
        "handoff_tickets",
    } <= tables
