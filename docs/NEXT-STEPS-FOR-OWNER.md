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
