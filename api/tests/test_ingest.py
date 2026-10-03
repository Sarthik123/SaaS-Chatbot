from pathlib import Path

import pytest

from app.db.memory import InMemoryRepository
from app.providers.fake import FakeEmbeddingProvider
from app.rag.chunking import embedding_input
from app.rag.ingest import IngestReport, ingest_directory, ingest_text, main, slugify, title_from

DIM = 16

LATE_FEES = (
    "# Late fees\n\n## Grace period\nThe grace period is 3 days.\n\n## The cap\nCapped at 25%.\n"
)
PASSWORDS = "# Reset your password\n\nUse the Forgot password link on the sign-in page.\n"


@pytest.fixture
def repo():
    return InMemoryRepository(DIM)


@pytest.fixture
def embedder():
    return FakeEmbeddingProvider(dim=DIM)


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "late-fees.md").write_text(LATE_FEES)
    (tmp_path / "Reset Password.md").write_text(PASSWORDS)
    (tmp_path / "notes.txt").write_text("Plain text article.\n\nSecond paragraph.")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")  # not an article: must be ignored
    return tmp_path


def test_slugify_and_title_helpers():
    assert slugify("Late Fees & Grace!") == "late-fees-grace"
    assert title_from("# My Title\n\nbody", "fallback") == "My Title"
    assert title_from("no heading here", "reset-password") == "Reset password"


def test_ingesting_a_folder_stores_articles_and_chunks(folder, repo, embedder):
    report = ingest_directory(folder, repo, embedder)
    assert report == IngestReport(files_read=3, articles=3, chunks=report.chunks, skipped=[])
    assert repo.count_articles() == 3
    assert repo.count_chunks() == report.chunks > 3  # late-fees alone has three chunks
    assert [a.slug for a in repo.list_articles()] == ["late-fees", "notes", "reset-password"]


def test_article_fields_are_filled_in(folder, repo, embedder):
    ingest_directory(folder, repo, embedder, base_url="https://help.example/")
    article = repo.get_article_by_slug("late-fees")
    assert article.title == "Late fees"
    assert article.source_url == "https://help.example/late-fees"
    assert article.body == LATE_FEES
    chunks = repo.list_chunks(article.id)
    # The title line has no text of its own, so there is one chunk per section below it.
    assert [c.heading for c in chunks] == ["Late fees > Grace period", "Late fees > The cap"]
    assert all(len(c.embedding) == DIM for c in chunks)


def test_headings_are_embedded_together_with_the_text(folder, repo, embedder):
    ingest_directory(folder, repo, embedder)
    article = repo.get_article_by_slug("late-fees")
    first = repo.list_chunks(article.id)[0]
    expected = embedder.embed([embedding_input(first.heading, first.text)])[0]
    assert first.embedding == expected


def test_running_ingestion_twice_does_not_create_duplicates(folder, repo, embedder):
    first = ingest_directory(folder, repo, embedder)
    counts = (repo.count_articles(), repo.count_chunks())
    ids = [a.id for a in repo.list_articles()]
    second = ingest_directory(folder, repo, embedder)
    assert (repo.count_articles(), repo.count_chunks()) == counts
    assert [a.id for a in repo.list_articles()] == ids
    assert (first.articles, first.chunks) == (second.articles, second.chunks)


def test_a_changed_file_replaces_the_old_chunks(folder, repo, embedder):
    ingest_directory(folder, repo, embedder)
    (folder / "late-fees.md").write_text("# Late fees\n\nNow there is only one short section.\n")
    ingest_directory(folder, repo, embedder)
    article = repo.get_article_by_slug("late-fees")
    chunks = repo.list_chunks(article.id)
    assert len(chunks) == 1
    assert "only one short section" in chunks[0].text


def test_empty_files_are_skipped_and_reported(tmp_path, repo, embedder):
    (tmp_path / "empty.md").write_text("")
    (tmp_path / "blank.md").write_text("   \n\n")
    (tmp_path / "title-only.md").write_text("# Just a title\n")
    (tmp_path / "ok.md").write_text("# Fine\n\nSome text.")
    report = ingest_directory(tmp_path, repo, embedder)
    assert report.files_read == 4
    assert report.articles == 1
    assert sorted(report.skipped) == ["blank.md", "empty.md", "title-only.md"]
    assert repo.count_articles() == 1


def test_ingest_text_returns_the_number_of_chunks(repo, embedder):
    count = ingest_text(repo, embedder, slug="a", body=LATE_FEES, source_url="https://x.example/a")
    assert count == 2  # one chunk for each of the two sections that have text
    assert ingest_text(repo, embedder, slug="b", body="", source_url="https://x.example/b") == 0
    assert repo.get_article_by_slug("b") is None


def test_a_provider_with_the_wrong_vector_size_gives_a_clear_error(repo):
    wrong = FakeEmbeddingProvider(dim=32)
    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        ingest_text(repo, wrong, slug="a", body=LATE_FEES, source_url="https://x.example/a")


def test_the_command_line_refuses_to_run_without_a_database(folder, capsys):
    exit_code = main([str(folder)])
    assert exit_code == 2
    assert "DATABASE_URL is not set" in capsys.readouterr().err


def test_the_command_line_reports_a_missing_folder(tmp_path, capsys):
    assert main([str(Path(tmp_path) / "nope")]) == 2
    assert "Folder not found" in capsys.readouterr().err
