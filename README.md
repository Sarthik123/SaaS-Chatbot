# SaaS AI Support Agent

A customer-support chatbot for software companies. It answers a customer's question using
**only the company's own help articles**, shows which article it used, and says
**"I don't know"** with a way to reach a human when the articles do not cover the question.

**Status: portfolio MVP. Fake demo data only. No real users.**

The demo company is a made-up invoicing app called "Acme Invoicing". All help articles in
`data/demo_kb/` are fake.

> Live demo: _see docs/NEXT-STEPS-FOR-OWNER.md for deployment steps_
> Screenshots: _take them after deploying_

---

## How it works (one question)

1. The customer types a question.
2. The backend turns it into a 768-number vector (its meaning).
3. It searches saved pieces ("chunks") of the help articles by meaning AND by keywords.
4. If nothing matches well enough it says "I don't know" and offers a human. **No AI call is made.**
5. Otherwise it sends the question and the best chunks to the AI model with strict rules.
6. The answer comes back with article links, which the app checks are real.
7. The app records speed, tokens (cost) and thumbs up/down.

Full technical explanation: [docs/EXPLAINER.md](docs/EXPLAINER.md)
Architecture diagram: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## What is built

| Phase | What | Status |
|---|---|---|
| 0 | Foundations: folders, config, health check, fake AI parts, CI | ✅ built |
| 1 | Knowledge base: database, 25 fake articles, ingestion | ✅ built |
| 2 | Brain: search, abstain-first, cited answers, /api/chat | ✅ built |
| 3 | Feedback, handoff, admin routes | ✅ built |
| 4 | Demo chat page (/demo), admin panel (/admin) | ✅ built |
| 5 | 30-question evaluation (evals/run.py) | ✅ built |
| 6 | Security and privacy docs, architecture, explainer | ✅ built |
| 7 | Dockerfile, deployment guide (Vercel + Render + Neon) | ✅ built |
| 8 | Final README, complete docs | ✅ built |

Detailed decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
What the owner decided vs. what the AI tool wrote: [docs/PROJECT-EVIDENCE.md](docs/PROJECT-EVIDENCE.md)

---

## Run it on your own computer

You need **Python 3.11 or newer**, **Node.js 22**, and **Docker** (for the local database).

```bash
# 1. Create your private settings file (it is never uploaded to GitHub)
cp .env.example .env

# 2. Backend: create a virtual environment and install packages
cd api && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Run the backend tests (they use fake AI parts: free, offline)
pytest -q

# 4. Start the backend  →  open http://localhost:8000/api/health
uvicorn app.main:app --reload --port 8000

# 5. In a second terminal: start the website  →  open http://localhost:3000
cd web && npm install && npm run dev
```

### Add the demo knowledge base (local database)

```bash
# from the repo root: start Postgres 16 with pgvector
docker compose up -d db

# in .env set:
# DATABASE_URL=postgresql://support:support@localhost:5432/support_agent
# LLM_PROVIDER=fake  (or cloudflare once you have keys — see docs/NEXT-STEPS-FOR-OWNER.md)

cd api
alembic upgrade head                                           # creates the tables
LLM_PROVIDER=fake python -m app.rag.ingest ../data/demo_kb   # loads the 25 fake articles
# run it twice: the count must be identical (no duplicates)
LLM_PROVIDER=fake python -m app.rag.ingest ../data/demo_kb
```

After ingesting articles, try the CLI:
```bash
cd api
LLM_PROVIDER=fake python -m app.cli ask --demo "how do I reset my password?"
```

### Run the eval set

```bash
cd api
LLM_PROVIDER=fake python ../evals/run.py        # free, fast, no real AI answers
LLM_PROVIDER=cloudflare python ../evals/run.py  # real answers (needs Cloudflare keys)
```

Results are written to `evals/results/latest.json` and `docs/EVALS.md`.

---

## Tests and checks

| Command | What it checks |
|---|---|
| `cd api && pytest -q` | All backend tests (224 passing, 42 skipped without a database) |
| `cd api && pytest -q -m integration` | Database contract tests (needs `DATABASE_URL`) |
| `cd api && ruff check .` | Python lint |
| `cd web && npm run lint` | TypeScript / Next.js lint |
| `cd web && npm run build` | Next.js build with TypeScript type-check |

GitHub Actions runs all of the above on every push (see `.github/workflows/ci.yml`).

---

## Deploy to the internet

You need accounts at Neon, Cloudflare, Vercel and Render (all free tiers).
Exact step-by-step instructions: [docs/NEXT-STEPS-FOR-OWNER.md](docs/NEXT-STEPS-FOR-OWNER.md).

Summary:

| Service | What goes there | How |
|---|---|---|
| **Neon** | Postgres database with pgvector | Create a project, copy the connection string |
| **Cloudflare Workers AI** | AI and embedding model | Create an account, add API token |
| **Render** | Python/FastAPI backend | Connect GitHub, pick `api/Dockerfile`, set env vars |
| **Vercel** | Next.js frontend | Connect GitHub, pick `web/` folder, set `NEXT_PUBLIC_API_URL` |

Environment variables needed on Render:

```
DATABASE_URL=          # Neon connection string
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
LLM_PROVIDER=cloudflare
LLM_MODEL=@cf/mistral/mistral-7b-instruct-v0.1
EMBEDDING_MODEL=@cf/baai/bge-base-en-v1.5
EMBEDDING_DIM=768
ADMIN_PASSWORD=        # choose a strong password
SESSION_SECRET=        # choose a random 32-character string
ALLOWED_ORIGINS=       # your Vercel URL, e.g. https://saas-chatbot.vercel.app
```

After deploying: ingest the articles once via the admin panel (Articles → Re-embed all).

---

## Limitations

- Fake company, fake articles, no real customers.
- Answer quality depends on the AI model chosen. Not yet measured with real keys.
- The code was written by an AI coding tool (Claude Code) under the owner's written
  specification ([AGENTS.md](AGENTS.md)); see [docs/PROJECT-EVIDENCE.md](docs/PROJECT-EVIDENCE.md).
- The rate limiter is per-process. Multiple API replicas each count separately.
- Session cookies expire after 7 days; there is no server-side revocation.
