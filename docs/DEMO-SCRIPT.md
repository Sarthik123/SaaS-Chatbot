# Demo script (3 minutes)

Use this script to walk a recruiter or interviewer through the live demo.
All questions are answered by the fake Acme Invoicing knowledge base.

---

## Before you start (30 seconds)

1. Open the demo page: `https://<your-vercel-url>/demo`
2. Make sure the chat bubble (bottom right) is visible.
3. Have the admin page ready in a second tab: `https://<your-vercel-url>/admin`

---

## Act 1 — a question it can answer (45 seconds)

Click the chat bubble. Ask:

> "How do I reset my password?"

**Point out:**
- The typing indicator (three bouncing dots) while it thinks.
- The answer cites a source chip — click it to see the exact quote.
- The thumbs-up / thumbs-down buttons.
- The amber "AI answers can be wrong" banner at the top.

---

## Act 2 — a follow-up question (30 seconds)

Without starting a new chat, ask:

> "What if the reset email doesn't arrive?"

**Point out:**
- The conversation id is the same (same thread).
- The bot used the same article because the follow-up question is in the same topic.

---

## Act 3 — a question it cannot answer (30 seconds)

Ask:

> "What is the capital of France?"

**Point out:**
- The bot says "I could not find that in our help articles…" — it does NOT guess.
- The "Talk to a human" link appears.
- Click it to show the handoff form (name, email, message).

---

## Act 4 — the admin panel (45 seconds)

Switch to the admin tab. Log in with your `ADMIN_PASSWORD`.

**Show:**
- **Articles tab**: the 25 fake help articles, with delete and reindex buttons.
- **Unanswered tab**: the "capital of France" question now appears here (abstained).
- **Tickets tab**: the handoff request you just submitted.
- **Stats tab**: total conversations, abstain rate, thumbs ratio.

---

## 30-second backup plan (if the live demo is down)

- Show the code: `api/app/rag/answer.py` — the six decision steps, each clearly commented.
- Show a test run: `cd api && python -m pytest tests/test_answer.py -v`
- Show the eval: `evals/results/latest.json` — the 30-question scores.

---

## Anticipated questions

| Question | Answer |
|---|---|
| "Is this using ChatGPT?" | No — it uses Cloudflare Workers AI (a free LLM). The provider interface means we can swap to OpenAI with one env-var change. |
| "What stops it from making things up?" | The abstain-first rule, the citation check, and the rule-leak check — all described in `docs/SECURITY-AND-PRIVACY.md`. |
| "How would you improve the accuracy?" | Run the eval, lower `MIN_SIMILARITY` for fewer false negatives, and improve the articles for false positives. |
| "Could you add a second company?" | Yes — deploy a second copy with its own database and `ALLOWED_ORIGINS`. Multi-tenancy in one DB is possible but needs row-level security. |
