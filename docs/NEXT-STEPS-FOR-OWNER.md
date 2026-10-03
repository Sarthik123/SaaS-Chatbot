# Next steps for the owner

Things only a human can do (create accounts, copy keys, click settings). Each step is numbered and
says exactly what to type. **Never paste a real key into a chat, a prompt or GitHub.**

## Now: check Phase 0 (5 minutes)

1. On GitHub open the repository `Sarthik123/SaaS-Chatbot`, then the **Actions** tab. The latest
   run named "CI" should have a green tick. If it is red, copy the first error line and give it
   to Claude Code.
2. On your computer, in a terminal, from the repo folder:
   1. `cp .env.example .env`
   2. `cd api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
   3. `pytest -q`  (you should see all tests pass)
   4. `uvicorn app.main:app --reload --port 8000`, then open <http://localhost:8000/api/health>
      (you should see `{"status":"ok"}`)
3. In a second terminal: `cd web && npm install && npm run dev`, then open <http://localhost:3000>
   (you should see "API: OK").

## Check Phase 1: the database and the demo articles (10 minutes)

You need Docker Desktop running for this.

1. From the repo folder: `docker compose up -d db` (starts a local Postgres with pgvector).
2. Open your `.env` file and set exactly this line (it is a throw-away local password):
   `DATABASE_URL=postgresql://support:support@localhost:5432/support_agent`
3. `cd api` and activate the virtual environment (`source .venv/bin/activate`).
4. `alembic upgrade head` (you should see "Running upgrade -> 0001").
5. `LLM_PROVIDER=fake python -m app.rag.ingest ../data/demo_kb`
   You should see "Read 25 files. Stored 25 articles and N chunks." (N was 162 when this was written.)
6. Run step 5 again. The numbers must be the same.
7. Open 3 files in `data/demo_kb/`. They should read like real help articles. Open
   `docs/KB-COVERAGE.md` and check both lists exist.
8. Optional: look at the rows. `docker compose exec db psql -U support -d support_agent -c "select slug from articles limit 5;"`

## Accounts you will need later (do these when you want to run with real AI, about 1 to 2 hours)

| Account | Needed from | Where it goes |
|---|---|---|
| Neon (free Postgres) | Phase 1 live check and Phase 7 | `DATABASE_URL` |
| Cloudflare (free Workers AI): Account ID and an API token that allows Workers AI | Phase 2 real answers | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| Vercel and Render (free) | Phase 7 | their "Environment variables" screens |

Exact click-by-click steps for each are added to this file in the phase that needs them.

## Optional: make the repository public

The guide says a public repo is fine because secrets never go into it. When you want recruiters to
read the code: GitHub, repo **Settings**, scroll to **Danger Zone**, **Change visibility**,
**Make public**. Do this only after the secrets check (added in Phase 7) passes.
