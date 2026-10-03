# Architecture

How the system is built, and why each part was chosen.

---

## High-level diagram

```
Browser
  │
  ├─ web/  (Next.js on Vercel)
  │    ├─ /           Home page (API status check)
  │    ├─ /demo       Fake company page + ChatWidget
  │    └─ /admin      Password-protected admin panel
  │
  │  HTTP (REST, JSON)
  │
  └─ api/  (FastAPI on Render)
       ├─ POST /api/chat
       ├─ POST /api/feedback
       ├─ POST /api/handoff
       ├─ GET  /api/health
       └─ /api/admin/*  (password-protected)
            │
            ├─ AI providers (Cloudflare Workers AI or OpenAI)
            │    EmbeddingProvider  →  embed a question or a chunk
            │    LLMProvider        →  generate an answer
            │
            └─ Postgres (Neon)  with pgvector
                 articles   — the help knowledge base
                 chunks      — searchable pieces of each article
                 conversations, messages  — chat history
                 feedback    — thumbs up/down
                 handoff_tickets  — "talk to a human" requests
```

---

## The path of one question

1. **Browser** sends `POST /api/chat { message: "how do I reset my password?" }`.
2. **Rate limiter** checks the visitor's salted-IP fingerprint: ≤ 20 messages per 10 min.
3. **Guardrails** trim and validate the question (≤ 500 chars), mask emails/phones/card numbers.
4. **Embedder** turns the question into a 768-number vector (meaning-numbers).
5. **Retrieval**:
   - Vector search: find the 8 chunks whose meaning is closest to the question's vector.
   - Keyword search: find the 8 chunks that contain the words of the question.
   - Merge both lists with reciprocal rank fusion; keep the top 5.
6. **Abstain check**: if no chunk has similarity ≥ MIN_SIMILARITY (default 0.35), return the
   fallback message immediately. The LLM is never called.
7. **LLM call**: send the top-5 chunks inside `<context>` tags, the last 4 messages as
   `<history>`, and the question inside `<question>` tags, plus a fixed rulebook.
8. **Validate**: the model must return JSON `{ can_answer, answer, used_chunk_ids }`.
   If the JSON is invalid, retry once. If still invalid, return the fallback.
9. **Citation check**: every chunk ID the model cited must be one we actually gave it.
   A hallucinated ID triggers the fallback.
10. **Rule-leak check**: if the answer contains phrases from the hidden rulebook, discard it.
11. **Save**: user message and assistant reply (with citations, latency, token counts) are
    saved to Postgres.
12. **Response**: `{ conversation_id, message_id, answer, citations, abstained, handoff_offered }`.

---

## Technology choices

| Technology | Why | Alternative |
|---|---|---|
| **Next.js (App Router)** | Server-side rendering, TypeScript, fast builds, Vercel deployment is one command | Create React App (no SSR), plain HTML |
| **FastAPI** | Python, async, automatic OpenAPI docs, Pydantic validation | Flask (no async), Django (heavier) |
| **PostgreSQL** | Reliable, `pgvector` extension for meaning-search in the same DB | Separate vector DB (Pinecone, Weaviate) — more moving parts |
| **pgvector HNSW index** | Fast approximate nearest-neighbour search, no training step | IVFFlat (needs `LISTS` tuning), Faiss (separate service) |
| **Cloudflare Workers AI** | Free tier, no credit card, works from a UK or US IP | OpenAI (paid, faster, higher quality) |
| **Reciprocal rank fusion** | Combines meaning-search and keyword-search fairly, no tuning | Weighted sum (needs calibrated weights), keyword only (misses paraphrases) |
| **Neon** | Free Postgres-as-a-service with pgvector, point-in-time restore | Supabase, Railway, Render Postgres (all fine) |
| **Render** | Free tier for the API container, simple Dockerfile deploy | Fly.io, Railway (both fine), Heroku (costs money) |
| **Vercel** | Free Next.js hosting, automatic preview deployments | Netlify, Cloudflare Pages (both fine) |
| **Alembic** | Standard SQLAlchemy migration tool, reversible | Django migrations (wrong framework), raw SQL files |
| **In-memory repository** | Tests run in milliseconds with no database | Always use Postgres (tests need a real DB, slower) |

---

## What is NOT in this architecture

- No background job queue (reindex is synchronous; fine for a demo with 25 articles).
- No caching layer (every question hits the DB; fine for a demo).
- No WebSockets (the chat is request-response, not streaming).
- No multi-tenant isolation (one company's articles per deployment).
