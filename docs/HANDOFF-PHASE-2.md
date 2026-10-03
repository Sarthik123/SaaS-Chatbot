# Phase 2 hand-off: where the work stopped

The full list of remaining phases (2 to 8) is in `docs/BUILD-PLAN-REMAINING.md`.

This branch holds Phase 2 ("Brain") **as written but not finished**. The code exists and
passes lint. The 106 tests from Phases 0 and 1 still pass. The Phase 2 code itself has
**no tests yet**, so treat it as unverified.

## What is already written (in `api/app/`)

- `providers/`: real Cloudflare and OpenAI providers (not tested against the live services),
  a shared web-call helper with timeout and one retry, and the fake providers.
- `db/`: keyword and meaning search plus conversation and message storage, in both the
  in-memory and Postgres repositories (`textsearch.py` is the shared keyword logic).
- `rag/guardrails.py`, `rag/retrieval.py`, `rag/answer.py`: the safety rules, the search
  merge and the answer rules (abstain first, JSON check, citation check).
- `security.py` (rate limiter), `routes/chat.py` (`POST /api/chat`), `main.py` wiring.
- `cli.py`: `python -m app.cli ask --demo "your question"` (run with `LLM_PROVIDER=fake`).

## What is still to do for Phase 2

1. Tests for everything above (the repository contract tests for search and messages,
   provider tests with fake web replies, guardrails, retrieval, the answer pipeline,
   the `/api/chat` route, the CLI). Follow the checks listed in the build guide.
2. Add decisions D20 and later to `docs/DECISIONS.md` (model choices and why, the
   "last 4 messages" reading, what the stored retrieved ids mean, OpenAI untested).
3. Update `docs/PROJECT-EVIDENCE.md`, `README.md`, `docs/NEXT-STEPS-FOR-OWNER.md`
   (Cloudflare account and token steps) and `.env.example`.
4. Run the whole suite with and without `DATABASE_URL`, then merge to `main`.

## Known limits (not hidden)

- CI results were never seen from the cloud workspace, so "CI is green" is not verified.
- The "API: OK" check in the browser has not been done.
- Nothing has been run against real Cloudflare or OpenAI keys.
