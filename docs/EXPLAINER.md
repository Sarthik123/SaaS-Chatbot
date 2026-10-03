# Explainer — plain-English guide to every idea in the project

For each technology and concept, this file gives:
- What it is in simple words
- Why it was used here
- Its main limit
- A non-technical way to say it
- A technical way to say it
- Two interview follow-up questions with honest answer outlines

---

## RAG — Retrieval-Augmented Generation

**Simple**: Before asking the AI a question, you look up the relevant pages in your
own knowledge base and paste them into the question. The AI is only allowed to answer
from those pages.

**Why here**: stops the AI from guessing or making up facts. Every answer can be traced
back to a specific article.

**Limit**: the AI can still misread an article, or an article can be wrong. The bot is
only as accurate as its knowledge base.

**Non-technical**: "We give the AI a cheat sheet, and it can only answer from the cheat sheet."

**Technical**: The model's context window includes retrieved document chunks. The model
is instructed to set `can_answer=false` when the context is insufficient.

**Interview follow-ups**:
1. *Why not just fine-tune the model on the articles?* Fine-tuning is expensive, slow, and
   the knowledge becomes stale the moment the articles change. RAG lets you update the
   knowledge base without retraining.
2. *What stops the model from ignoring the context and answering from its training data?*
   The system prompt forbids it. In practice this reduces (not eliminates) the risk. The
   guardrails (citation check, rule-leak check) catch many failures.

---

## Embeddings

**Simple**: Turn a piece of text into a list of 768 numbers that captures its meaning.
Two pieces of text that mean the same thing produce similar number lists.

**Why here**: lets you search for articles by what they mean ("how do I get my money
back?") even if they use different words ("refund policy").

**Limit**: the embedding model is trained on a fixed set of words. Technical jargon
specific to your product may not embed well.

**Non-technical**: "We translate every sentence into a secret number code; similar
sentences get similar codes."

**Technical**: Each chunk is embedded into a 768-dimensional unit vector using
`@cf/baai/bge-base-en-v1.5`. Similarity is cosine distance.

**Interview follow-ups**:
1. *What dimension did you choose and why?* 768 — it is the output size of the default
   Cloudflare embedding model. Changing the model requires re-embedding everything.
2. *How did you pick the embedding model?* We needed a free Cloudflare model that works
   well on English text. BGE-base-en-v1.5 is a well-benchmarked multilingual model in
   the MTEB leaderboard.

---

## Chunking

**Simple**: Split a long article into smaller overlapping pieces so the AI receives
the most relevant piece, not the whole document.

**Why here**: LLMs have a limited context window. Sending a whole article is wasteful
and the irrelevant parts dilute the relevant ones.

**Limit**: a question that spans two sections may not get a single chunk that covers
both. Overlap (50 tokens) reduces but does not eliminate this.

**Non-technical**: "We cut each help article into paragraphs so the bot only reads
the part of the article it actually needs."

**Technical**: Split at headings first, then at ~350-token boundaries with ~50-token
overlap. Each chunk keeps its heading so retrieval knows which section it came from.

---

## Hybrid retrieval (vector + keyword)

**Simple**: Two searches run at once — one by meaning, one by exact word match. The
results are merged.

**Why here**: meaning-search finds paraphrases but misses exact codes ("ERR-5003").
Keyword-search finds exact codes but misses paraphrases. Together they are better than
either alone.

**Limit**: the merge uses a simple scoring formula (RRF). It does not learn weights
from user feedback.

**Non-technical**: "We search both the dictionary and the encyclopedia at the same time."

**Technical**: Reciprocal rank fusion (RRF, k=60). Top 8 from each search, merged,
top 5 kept. MIN_SIMILARITY gates whether any chunk reaches the LLM.

---

## Reciprocal rank fusion (RRF)

**Simple**: A way to combine two ranked lists. A result that appears high in either list
(or in both) gets a high combined score.

**Why here**: no need to tune weights or normalize scores across two very different
search systems.

**Limit**: RRF treats both lists as equally trustworthy. If keyword search produces
very poor results (e.g., the query is pure stop-words), those results still enter the
final set.

**Non-technical**: "We give each result points based on where it appears in each list,
then add up the points."

**Technical**: `score(d) = 1/(k+rank_vector) + 1/(k+rank_keyword)`. k=60 is the
standard constant that softens the effect of very high ranks.

---

## The abstain-first rule

**Simple**: if nothing in the knowledge base looks relevant enough, the bot says
"I don't know" and offers a human, without ever calling the expensive AI model.

**Why here**: saves money (no LLM call), avoids hallucinations, and is honest.

**Limit**: if MIN_SIMILARITY is set too high, the bot refuses to answer questions that
are actually covered.

**Non-technical**: "The bot checks its notes before asking the teacher. If there is
nothing relevant in the notes, it asks a human directly."

**Technical**: `if not context: return fallback`. The LLM is never called.

---

## Cloudflare Workers AI

**Simple**: Cloudflare runs AI models in its global network. You call a REST API, pay
(or use the free tier), and get an answer.

**Why here**: free tier, no credit card needed, instant setup. Good enough for a demo.

**Limit**: the free-tier models are smaller than GPT-4. Answer quality is noticeably
lower on complex or ambiguous questions.

**Non-technical**: "We borrowed a brain from Cloudflare's free library."

**Technical**: REST API: `POST /accounts/{id}/ai/run/@cf/mistral/mistral-7b-instruct-v0.1`.
The provider interface makes it swappable with OpenAI via `LLM_PROVIDER=openai`.

---

## pgvector

**Simple**: a Postgres extension that adds a "vector" column type and lets you search
by cosine similarity in SQL.

**Why here**: keeps the vector search in the same database as the rest of the data.
No extra service to run or pay for.

**Limit**: HNSW indexes are approximate (they may miss the truly nearest neighbour in
rare cases). For a knowledge base of < 100 000 chunks this is not a problem in practice.

---

## GitHub Actions CI

**Simple**: every time you push code, GitHub runs your tests automatically and shows a
green or red badge.

**Why here**: catches broken tests before anyone sees the code.

**Limit**: CI only runs the checks that are written. Untested code can still break.

---

## FastAPI + Pydantic

**Simple**: FastAPI builds the REST API. Pydantic validates every input automatically
and rejects bad data with a clear error message.

**Why here**: Pydantic validation + FastAPI's auto-docs make the API contract explicit
and testable.

---

## The in-memory repository

**Simple**: a fake database that lives in the program's memory. Used in tests so they
run in milliseconds without a real database.

**Why here**: fast tests. The same tests run against the real Postgres too (integration
tests, skipped when `DATABASE_URL` is not set).

**Limit**: it is a fake. If the Postgres version behaves differently, only the
integration tests will catch it.

---

## Interview question bank

| Question | Honest one-liner answer |
|---|---|
| Why not use a vector database like Pinecone? | pgvector keeps everything in one DB (simpler ops). For this scale (<100k chunks) it is fast enough. |
| How do you prevent the AI from making things up? | RAG + citation check + abstain-first. Hallucinations are reduced, not eliminated. |
| What would you change for production scale? | Background job queue for reindex, connection pooling (PgBouncer), streaming responses, eval-driven threshold tuning. |
| What is the worst-case security failure? | A clever prompt-injection attack that bypasses tag stripping on a weak model. The mitigation is a stronger model + output validation. |
| How would you add a second company? | Each company gets its own deployment (separate DB). Multi-tenant in one DB is possible but adds row-level security complexity. |
