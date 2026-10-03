"""Tests for the retrieval layer (rag/retrieval.py).

All tests use InMemoryRepository and FakeEmbeddingProvider, so they run with no
database and no internet.
"""

import pytest

from app.db.memory import InMemoryRepository
from app.db.repository import NewChunk
from app.providers.fake import FakeEmbeddingProvider
from app.rag.retrieval import FINAL_TOP_K, RetrievalResult, RetrievedChunk, fuse, retrieve

DIM = 64


def make_repo() -> InMemoryRepository:
    return InMemoryRepository(DIM)


def make_embedder() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dim=DIM)


def vec(seed: float) -> list[float]:
    """A unit-length vector offset by `seed`.  Good enough for testing."""
    import math

    raw = [seed + i / 100 for i in range(DIM)]
    length = math.sqrt(sum(x * x for x in raw))
    return [x / length for x in raw]


def add_article(repo, slug, text, heading="") -> tuple[int, int]:
    """Add an article with one chunk and return (article_id, chunk_id)."""
    embedder = FakeEmbeddingProvider(dim=DIM)
    (embedding,) = embedder.embed([heading + "\n" + text])
    article = repo.upsert_article(
        slug=slug,
        title=slug.replace("-", " ").title(),
        source_url=f"https://help.example/{slug}",
        body=text,
        chunks=[NewChunk(chunk_index=0, heading=heading, text=text, token_count=10, embedding=embedding)],
    )
    chunk_id = repo.list_chunks(article.id)[0].id
    return article.id, chunk_id


# ---------- fuse ----------


def _hit(chunk_id, similarity):
    """Build a minimal ChunkHit for fuse() testing."""
    from app.db.repository import ChunkHit

    return ChunkHit(
        chunk_id=chunk_id,
        article_id=1,
        chunk_index=0,
        heading="h",
        text="t",
        token_count=5,
        article_title="A",
        article_slug="a",
        source_url="https://x",
        similarity=similarity,
    )


def test_fuse_deduplicates_chunks_present_in_both_lists():
    shared = _hit(1, similarity=0.9)
    vector_hits = [shared, _hit(2, similarity=0.7)]
    keyword_hits = [shared, _hit(3, similarity=0.5)]
    result = fuse(vector_hits, keyword_hits, min_similarity=0.0, final_k=10)
    ids = [c.hit.chunk_id for c in result]
    assert len(ids) == len(set(ids)), "same chunk_id appeared twice"


def test_fuse_keeps_at_most_final_k_chunks():
    hits = [_hit(i, similarity=1.0 / (i + 1)) for i in range(20)]
    result = fuse(hits, [], min_similarity=0.0, final_k=5)
    assert len(result) <= 5


def test_fuse_chunk_in_both_lists_scores_higher_than_chunk_in_one_list():
    both = _hit(1, similarity=0.5)
    only_vector = _hit(2, similarity=0.99)  # higher similarity but only in one list
    result = fuse([both, only_vector], [both], min_similarity=0.0, final_k=10)
    ids_in_order = [c.hit.chunk_id for c in result]
    assert ids_in_order.index(1) < ids_in_order.index(2)


def test_fuse_marks_passes_correctly():
    hits = [_hit(1, similarity=0.8), _hit(2, similarity=0.2)]
    result = fuse(hits, [], min_similarity=0.5, final_k=10)
    by_id = {c.hit.chunk_id: c for c in result}
    assert by_id[1].passes is True
    assert by_id[2].passes is False


def test_fuse_records_vector_rank_and_keyword_rank():
    v1 = _hit(1, similarity=0.9)
    k1 = _hit(2, similarity=0.8)
    result = fuse([v1], [k1], min_similarity=0.0, final_k=10)
    by_id = {c.hit.chunk_id: c for c in result}
    assert by_id[1].vector_rank == 1
    assert by_id[1].keyword_rank is None
    assert by_id[2].keyword_rank == 1
    assert by_id[2].vector_rank is None


# ---------- retrieve ----------


def test_retrieve_returns_a_retrieval_result():
    repo = make_repo()
    embedder = make_embedder()
    add_article(repo, "password-reset", "reset your password in settings")
    result = retrieve("reset password", repo, embedder, min_similarity=0.0)
    assert isinstance(result, RetrievalResult)
    assert len(result.chunks) >= 1


def test_retrieve_empty_repo_returns_no_chunks():
    repo = make_repo()
    embedder = make_embedder()
    result = retrieve("anything", repo, embedder, min_similarity=0.0)
    assert result.chunks == []
    assert result.context == []


def test_retrieve_context_only_includes_chunks_above_threshold():
    repo = make_repo()
    embedder = make_embedder()
    # Insert a chunk about invoices; asking about passwords will have low similarity.
    add_article(repo, "invoices", "monthly invoice export csv billing cycle")
    result = retrieve("password reset help", repo, embedder, min_similarity=0.99)
    # With a threshold of 0.99, nothing about invoices should match a password question.
    assert result.context == []


def test_retrieve_question_is_stored_in_result():
    repo = make_repo()
    embedder = make_embedder()
    result = retrieve("how to cancel subscription", repo, embedder, min_similarity=0.0)
    assert result.question == "how to cancel subscription"


def test_retrieval_result_best_similarity_is_none_when_empty():
    result = RetrievalResult(question="q", min_similarity=0.5, chunks=[])
    assert result.best_similarity is None


def test_retrieval_result_with_threshold_reapplies_passes():
    from app.db.repository import ChunkHit

    hit = ChunkHit(
        chunk_id=1, article_id=1, chunk_index=0, heading="h", text="t", token_count=5,
        article_title="A", article_slug="a", source_url="https://x", similarity=0.7,
    )
    chunk = RetrievedChunk(hit=hit, vector_rank=1, keyword_rank=None, rrf_score=0.5, passes=True)
    original = RetrievalResult(question="q", min_similarity=0.35, chunks=[chunk])
    # Raise the threshold above the chunk's similarity
    stricter = original.with_threshold(0.9)
    assert stricter.chunks[0].passes is False
