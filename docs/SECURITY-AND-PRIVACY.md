# Security and privacy

An honest list of what the bot does to stay safe, and what it does NOT do.
No invented claims. Every item here maps to real code.

---

## What is actually built

### Input limits

| Rule | Where | Code |
|---|---|---|
| Questions are cut off at 500 characters | Before any processing | `api/app/rag/guardrails.py clean_question` |
| The FastAPI field limit is 5 000 characters (belt-and-suspenders) | HTTP layer | `api/app/routes/chat.py ChatRequest.message` |

### Personal data masking

Emails, phone numbers (9–15 digits) and card-like numbers (13–19 consecutive digits) in visitor
messages are replaced with `[email]`, `[phone]` or `[card]` **before the message is saved to the
database and before it is sent to the AI provider**.

Code: `api/app/rag/guardrails.py mask_personal_data`.

Limit: these are regex checks. They catch common formats. A visitor who writes an email as
`user [at] example.com` will not have it masked. Medical records, SSNs and other sensitive data
are not specifically detected.

### Prompt injection defence

Visitor messages and article text are treated as DATA, never as instructions. Two layers:

1. **Tag stripping**: anything in the visitor's message that looks like our own
   `<question>`, `<context>` or `<history>` XML tags is replaced with `[tag removed]`
   before it reaches the LLM prompt. This stops an attacker from closing the data box early
   and injecting instructions.
   Code: `api/app/rag/guardrails.py neutralize_tags`.

2. **Rulebook leak check**: if the model's answer contains phrases from our hidden
   rulebook (`used_chunk_ids`, `can_answer`, `<context`, etc.), the answer is discarded
   and the fallback message is returned instead.
   Code: `api/app/rag/guardrails.py looks_like_rule_leak`.

Limit: these are simple substring checks. A sophisticated adversarial prompt that avoids
these exact phrases could still manipulate a weaker model. The defence is good enough for a
portfolio demo but should be reviewed before a production deployment.

### Citation grounding

The bot only cites chunk IDs that were actually retrieved. If the model hallucinates a chunk
ID that was not in the retrieved set, the answer is discarded.
Code: `api/app/rag/answer.py answer_question` (citation_not_retrieved check).

### Rate limiting

20 messages per IP per 10 minutes (sliding window). Configurable via `RATE_LIMIT_MESSAGES`
and `RATE_LIMIT_WINDOW_SECONDS`. IP addresses are never stored: only a salted SHA-256 hash
is used as the rate-limit key.
Code: `api/app/security.py RateLimiter`, `hash_ip`.

Limit: the limiter is in memory (one process). With multiple API processes, each counts
separately. On Render's free tier this is one process, so it is fine for the demo.

### CORS

The API only accepts cross-origin requests from the addresses in `ALLOWED_ORIGINS`.
Credentials (the admin cookie) are never shared with other origins.
Code: `api/app/main.py CORSMiddleware`.

### Admin authentication

The admin area requires a password from `ADMIN_PASSWORD`. The password is never stored in
the database or in code. The session is an httpOnly cookie (JavaScript cannot read it) that
contains an HMAC-SHA256 token of the password. If `ADMIN_PASSWORD` is empty, every admin
endpoint returns 503.
Code: `api/app/routes/admin.py _make_token`, `_require_admin`.

Limit: the admin session does not expire on its own (it has a 7-day max-age). Log out
explicitly after each session. There is no session revocation (for example after a password
change) in this version.

### Auto-delete conversations

Conversations are not yet auto-deleted (configurable retention is planned for the production
deployment). On Neon the free tier prunes data after 7 days of inactivity by default.

---

## What is NOT built (known limits)

| Limitation | Note |
|---|---|
| Answer quality guarantee | The bot answers only from its articles, but regex prompt-injection defence is not foolproof on weak models. |
| Phone-number masking is heuristic | Fewer than 9 digits are not masked (too many order numbers). Some international formats may not match. |
| Rate limiter is per-process | Multiple API replicas each count separately. Acceptable on a single-process free-tier deploy. |
| No HTTPS enforcement in code | HTTPS is handled by Render (the host). The app itself does not redirect HTTP to HTTPS. |
| No CSP headers | The frontend is a Next.js app on Vercel; Vercel sets security headers by default. |
| No audit log | Admin actions (delete article, reindex) are not logged to a durable store. |
| No session revocation | Changing `ADMIN_PASSWORD` does not invalidate existing cookies until they expire. |
| No multi-tenant isolation | One deployment serves one company's articles. Do not add multiple companies' data to the same instance. |

---

## AGENTS.md safety rules implemented

From `AGENTS.md` § "RAG rules" item 7:

- [x] Limit question length to 500 characters
- [x] Rate limit 20 messages per 10 minutes per IP
- [x] Restrict CORS to configured origins
- [x] Mask emails, phone numbers and card-like numbers before saving
- [ ] Auto-delete conversations after 30 days — *not yet implemented (scheduled for the production Neon setup)*
- [x] Show a notice in the chat that AI answers can be wrong (in the `ChatWidget` amber banner)
