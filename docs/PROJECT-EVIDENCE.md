# Project evidence

An honest record of who did what. **All code in this repository was written by an AI coding tool
(Claude Code, by Anthropic) under the owner's written specification (`AGENTS.md`) and the owner's
verification.** The demo uses fake data and there are no real users.

"Owner verified" stays at **Pending** until the owner has personally run the check. The AI tool
runs tests too, but its own test runs are listed separately so they are never mistaken for the
owner's verification.

| Area | What the owner decided or specified | What the owner verified (command and result) | What the AI coding tool wrote | What the AI tool ran (not owner verification) |
|---|---|---|---|---|
| Product definition | What to build, who it is for, scope and out-of-scope, the "I don't know" rule, the rules in `AGENTS.md`, the nine-phase plan | Pending | Nothing (the specification is the owner's) | n/a |
| Phase 0: backend skeleton | Settings from environment variables; app must start with empty keys; fake and real providers behind two interfaces; CORS limited to configured origins | Pending: `cd api && pytest -q`, open `http://localhost:8000/api/health` | `api/app/config.py`, `main.py`, `routes/health.py`, `providers/*`, `api/tests/*` | `pytest -q` and `ruff check .` pass |
| Phase 0: website skeleton | Home page titled "Support Agent" showing `API: OK` or `API: not reachable` | Pending: open `http://localhost:3000` | `web/app/page.tsx`, `web/components/ApiStatus.tsx`, `web/lib/api.ts` | See the commit message for this phase |
| Phase 0: automation | Tests and checks must run on every push; no secrets in the repo | Pending: GitHub, Actions tab, latest run is green | `.github/workflows/ci.yml`, `.gitignore`, `.env.example`, `docker-compose.yml`, `db/init.sql`, `README.md`, `docs/` skeletons | n/a |
