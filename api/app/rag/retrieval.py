"""Retrieval: finding the help-article pieces that might answer a question.

Two searches run side by side:
  * by MEANING (embeddings): finds "How do I get my money back?" even if the article says
    "refund". It can miss exact things such as an error code.
  * by KEYWORDS (Postgres full-text search): finds "ERR-5003" exactly. It misses paraphrases.

Each search returns its best 8 chunks. We merge the two lists with "reciprocal rank fusion"
(a chunk ranked high in either list, or in both, scores well) and keep the best 5.

Finally MIN_SIMILARITY decides what is good enough to show to the AI model. If nothing passes,
the caller says "I don't know" and never calls the model (cheaper, and it cannot guess).
"""

from dataclasses import dataclass

from app.db.repository import ChunkHit, Repository
from app.providers.base import EmbeddingProvider

VECTOR_TOP_K = 8
KEYWORD_TOP_K = 8
FINAL_TOP_K = 5
RRF_K = 60  # the usual constant for reciprocal rank fusion; a bigger number flattens the ranking


@dataclass(frozen=True)
class RetrievedChunk:
    hit: ChunkHit
    vector_rank: int | None  # 1 = best by meaning; None = not in the meaning list
    keyword_rank: int | None  # 1 = best by keywords; None = not in the keyword list
    rrf_score: float
    passes: bool  # similarity >= MIN_SIMILARITY

    @property
    def similarity(self) -> float:
        return self.hit.similarity


@dataclass(frozen=True)
class RetrievalResult:
    question: str
    min_similarity: float
    chunks: list[RetrievedChunk]  # the best 5, best first, whether or not they pass

    @property
    def context(self) -> list[RetrievedChunk]:
        """The chunks good enough to give to the AI model."""
        return [chunk for chunk in self.chunks if chunk.passes]

    @property
    def best_similarity(self) -> float | None:
        return max((c.similarity for c in self.chunks), default=None)

    def with_threshold(self, min_similarity: float) -> "RetrievalResult":
        """The same result judged against another MIN_SIMILARITY (used by the eval sweep)."""
        return RetrievalResult(
            question=self.question,
            min_similarity=min_similarity,
            chunks=[
                RetrievedChunk(
                    hit=c.hit,
                    vector_rank=c.vector_rank,
                    keyword_rank=c.keyword_rank,
                    rrf_score=c.rrf_score,
                    passes=c.similarity >= min_similarity,
                )
                for c in self.chunks
            ],
        )


def fuse(
    vector_hits: list[ChunkHit],
    keyword_hits: list[ChunkHit],
    min_similarity: float,
    final_k: int = FINAL_TOP_K,
    rrf_k: int = RRF_K,
) -> list[RetrievedChunk]:
    """Merge the two ranked lists with reciprocal rank fusion and keep the best `final_k`."""
    scores: dict[int, float] = {}
    hits: dict[int, ChunkHit] = {}
    vector_rank: dict[int, int] = {}
    keyword_rank: dict[int, int] = {}
    for rank, hit in enumerate(vector_hits, start=1):
        vector_rank[hit.chunk_id] = rank
        hits[hit.chunk_id] = hit
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, hit in enumerate(keyword_hits, start=1):
        keyword_rank[hit.chunk_id] = rank
        # Prefer the keyword copy of a hit: it carries the keyword score too.
        hits[hit.chunk_id] = hit
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    ordered = sorted(scores, key=lambda cid: (-scores[cid], -hits[cid].similarity, cid))
    return [
        RetrievedChunk(
            hit=hits[cid],
            vector_rank=vector_rank.get(cid),
            keyword_rank=keyword_rank.get(cid),
            rrf_score=scores[cid],
            passes=hits[cid].similarity >= min_similarity,
        )
        for cid in ordered[:final_k]
    ]


def retrieve(
    question: str,
    repo: Repository,
    embedder: EmbeddingProvider,
    *,
    min_similarity: float,
    vector_k: int = VECTOR_TOP_K,
    keyword_k: int = KEYWORD_TOP_K,
    final_k: int = FINAL_TOP_K,
) -> RetrievalResult:
    """Search by meaning and by keywords, merge, keep the best chunks."""
    (embedding,) = embedder.embed([question])
    vector_hits = repo.search_vector(embedding, vector_k)
    keyword_hits = repo.search_keyword(question, embedding, keyword_k)
    chunks = fuse(vector_hits, keyword_hits, min_similarity, final_k=final_k)
    return RetrievalResult(question=question, min_similarity=min_similarity, chunks=chunks)
