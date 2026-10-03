# SaaS AI Support Agent

A customer-support chatbot for software companies. It answers a customer's question using
**only the company's own help articles**, shows which article it used, and says
**"I don't know"** with a way to reach a human when the articles do not cover the question.

**Status: portfolio MVP in progress. Fake demo data only. No real users.**

The demo company is a made-up invoicing app called "Acme Invoicing". All help articles in
`data/demo_kb/` are fake.

> Live link: _not deployed yet_  
> Screenshots: _not added yet_

## How it works (one question)

1. The customer types a question.
2. The backend turns it into an embedding (numbers that capture its meaning).
3. It searches saved pieces ("chunks") of the help articles by meaning and by keywords.
4. If nothing matches well enough it says "I don't know" and offers a human. No AI call is made.
5. Otherwise it sends the question and the best chunks to the AI model with strict rules.
6. The answer comes back with article links, which the app checks are real.
7. The app records speed, tokens (cost) and thumbs up/down.

## What is built so far

| Phase | What | Status |
|---|---|---|
| 0 | Foundations: folders, config, health check, fake AI parts, CI | built |
| 1 | Knowledge base: database, 25 fake articles, ingestion | built |
| 2 | Brain: search, abstain-first, cited answers | not started |
| 3 | Chat page, citations, human handoff, thumbs | not started |
| 4 | Admin area | not started |
| 5 | 30-question evaluation | not started |
| 6 | Security and privacy hardening | not started |
| 7 | Deployment (Vercel + Render + Neon) | not started |
| 8 | Written explanation documents | not started |

Detailed decisions: [docs/DECISIONS.md](docs/DECISIONS.md). What the owner decided versus what
the AI coding tool wrote: [docs/PROJECT-EVIDENCE.md](docs/PROJECT-EVIDENCE.md).

## Run it on your own computer

You need **Python 3.11 or newer** (tested on 3.12 in CI and 3.13 locally), **Node.js 22**,
and Docker (only needed from Phase 1, for the local database).

```bash
# 1. Create your private settings file (it is never uploaded to GitHub)
cp .env.example .env

# 2. Backend: create a virtual environment and install packages
cd api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt

# 3. Run the backend tests (they use fake AI parts: free, offline)
pytest -q

# 4. Start the backend  ->  open http://localhost:8000/api/health  (you should see {"status":"ok"})
uvicorn app.main:app --reload --port 8000

# 5. In a second terminal, start the website  ->  open http://localhost:3000 (you should see "API: OK")
cd web && npm install && npm run dev
```

### Local database and the demo articles (Phase 1)

```bash
# from the repo root: start Postgres 16 with pgvector
docker compose up -d db

# in .env set:  DATABASE_URL=postgresql://support:support@localhost:5432/support_agent
# then, from the api/ folder (virtual environment active):
cd api
alembic upgrade head                                  # creates the tables
LLM_PROVIDER=fake python -m app.rag.ingest ../data/demo_kb   # loads the 25 fake articles
```

The ingest command prints how many articles and chunks it stored. Run it a second time: the
numbers must stay the same (no duplicates). `LLM_PROVIDER=fake` uses the free fake embeddings;
real embeddings arrive in Phase 2. Use the same `EMBEDDING_DIM` for the migration and for ingestion.

Backend tests that need the database (marked `integration`) run when `DATABASE_URL` is set:
`DATABASE_URL=postgresql://support:support@localhost:5432/support_agent pytest -q`.
They create and delete their own private schema, so they never touch your real tables.

## Tests and checks

- Backend: `cd api && pytest -q` and `ruff check .`
- Website: `cd web && npm run lint && npm run build`
- GitHub Actions runs all of the above on every push (see `.github/workflows/ci.yml`).

## Limitations

- Fake company, fake articles, no real customers.
- Answer quality has **not been measured yet**. The 30-question test arrives in Phase 5.
- The code was written by an AI coding tool (Claude Code) under the owner's written
  specification ([AGENTS.md](AGENTS.md)); see [docs/PROJECT-EVIDENCE.md](docs/PROJECT-EVIDENCE.md).
