"""Ingestion: read help articles, chunk them, embed them, store them.

Run it from the api/ folder (DATABASE_URL must be set):

    python -m app.rag.ingest ../data/demo_kb

Running it twice is safe: an article is identified by its slug (the file name), so the second
run updates the same articles instead of adding copies.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.db import Repository, build_repository
from app.db.repository import NewChunk
from app.providers import build_embedding_provider
from app.providers.base import EmbeddingProvider
from app.rag.chunking import (
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    chunk_markdown,
    embedding_input,
)

DEFAULT_BASE_URL = "https://help.acme-invoicing.example"
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}
EMBED_BATCH_SIZE = 32  # texts sent to the embedding model per request

_TITLE = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass
class IngestReport:
    files_read: int = 0
    articles: int = 0
    chunks: int = 0
    skipped: list[str] = field(default_factory=list)  # files with no usable text


def slugify(name: str) -> str:
    """'Late Fees & Grace!' -> 'late-fees-grace'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def title_from(markdown: str, fallback: str) -> str:
    """The article title = its first '# Heading'; otherwise the file name made readable."""
    match = _TITLE.search(markdown)
    if match:
        return match.group(1).strip()
    return fallback.replace("-", " ").replace("_", " ").strip().capitalize()


def embed_in_batches(embedder: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        vectors.extend(embedder.embed(texts[start : start + EMBED_BATCH_SIZE]))
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Embedding provider returned {len(vectors)} vectors for {len(texts)} texts."
        )
    return vectors


def ingest_text(
    repo: Repository,
    embedder: EmbeddingProvider,
    *,
    slug: str,
    body: str,
    source_url: str,
    title: str | None = None,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> int:
    """Chunk, embed and store one article (replacing it if the slug exists).

    Returns the number of chunks stored (0 means the text had nothing to index and nothing was
    stored). The admin page (Phase 4) uses this same function for upload and reindex.
    """
    title = title or title_from(body, slug)
    chunks = chunk_markdown(
        body, fallback_title=title, target_tokens=target_tokens, overlap_tokens=overlap_tokens
    )
    if not chunks:
        return 0
    vectors = embed_in_batches(embedder, [embedding_input(c.heading, c.text) for c in chunks])
    repo.upsert_article(
        slug=slug,
        title=title,
        source_url=source_url,
        body=body,
        chunks=[
            NewChunk(
                chunk_index=chunk.chunk_index,
                heading=chunk.heading,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )
    return len(chunks)


def ingest_directory(
    directory: Path,
    repo: Repository,
    embedder: EmbeddingProvider,
    base_url: str = DEFAULT_BASE_URL,
) -> IngestReport:
    """Ingest every Markdown/text file in a folder."""
    report = IngestReport()
    base_url = base_url.rstrip("/")
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        report.files_read += 1
        slug = slugify(path.stem)
        count = ingest_text(
            repo,
            embedder,
            slug=slug,
            body=path.read_text(encoding="utf-8"),
            source_url=f"{base_url}/{slug}",
        )
        if count == 0:
            report.skipped.append(path.name)
        else:
            report.articles += 1
            report.chunks += count
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load help articles into the database.")
    parser.add_argument("directory", type=Path, help="folder with .md or .txt articles")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="start of each article's link")
    args = parser.parse_args(argv)

    if not args.directory.is_dir():
        print(f"Folder not found: {args.directory}", file=sys.stderr)
        return 2
    settings = get_settings()
    if not settings.database_url.get_secret_value():
        print(
            "DATABASE_URL is not set, so there is nowhere to store the articles.\n"
            "Set it in your .env file (see .env.example) and run the migration first:\n"
            "    alembic upgrade head",
            file=sys.stderr,
        )
        return 2

    repo = build_repository(settings)
    embedder = build_embedding_provider(settings)
    report = ingest_directory(args.directory, repo, embedder, base_url=args.base_url)

    print(
        f"Read {report.files_read} files. "
        f"Stored {report.articles} articles and {report.chunks} chunks."
    )
    if report.skipped:
        print(f"Skipped (no text): {', '.join(report.skipped)}")
    print(
        f"The database now holds {repo.count_articles()} articles and {repo.count_chunks()} chunks."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
