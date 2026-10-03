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
