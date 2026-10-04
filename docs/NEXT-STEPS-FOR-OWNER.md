# Next steps for the owner

Everything is built and tested. These are the only things left that require a human to create accounts and copy keys.

---

## 1. Get a Cloudflare Workers AI key (free, ~10 min)

1. Sign up at [dash.cloudflare.com](https://dash.cloudflare.com).
2. Your account ID is in the URL after login: `dash.cloudflare.com/<account-id>`. Copy it.
3. Top-right → **Profile** → **API Tokens** → **Create Token** → **Create Custom Token**.
4. Name it anything. Add permission: **Account → Workers AI → Edit**. Create and copy the token (shown once).
5. In the left sidebar click **AI** and confirm Workers AI is listed.

You now have `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.

---

## 2. Create the database on Neon (free, ~5 min)

1. Sign up at [neon.tech](https://neon.tech). Click **New project**, name it `saas-chatbot`.
2. Copy the **Connection string** from the dashboard. This is your `DATABASE_URL`.
3. Open **SQL editor** and run: `CREATE EXTENSION IF NOT EXISTS vector;` → click Run.

---

## 3. Deploy the API on Render (free, ~15 min)

1. Sign up at [render.com](https://render.com) with GitHub.
2. **New → Web Service** → connect the `SaaS-Chatbot` repo.
3. Set: Runtime = **Docker**, Dockerfile path = `api/Dockerfile`, Instance = **Free**.
4. Add these environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon connection string |
   | `CLOUDFLARE_ACCOUNT_ID` | from step 1 |
   | `CLOUDFLARE_API_TOKEN` | from step 1 |
   | `LLM_PROVIDER` | `cloudflare` |
   | `LLM_MODEL` | `@cf/mistral/mistral-7b-instruct-v0.1` |
   | `EMBEDDING_MODEL` | `@cf/baai/bge-base-en-v1.5` |
   | `EMBEDDING_DIM` | `768` |
   | `ADMIN_PASSWORD` | choose any strong password |
   | `SESSION_SECRET` | any 32 random characters |
   | `ALLOWED_ORIGINS` | your Vercel URL (fill in after step 4) |

5. Click **Create Web Service**. Wait for `Application startup complete.` in the deploy log.
6. Copy the URL Render gives you, e.g. `https://saas-chatbot-api.onrender.com`.

---

## 4. Deploy the website on Vercel (free, ~5 min)

1. Sign up at [vercel.com](https://vercel.com) with GitHub.
2. **Add New Project** → import `SaaS-Chatbot` → set Root Directory to `web`.
3. Add environment variable: `NEXT_PUBLIC_API_URL` = the Render URL from step 3.6.
4. Click **Deploy**. Copy your Vercel URL, e.g. `https://saas-chatbot.vercel.app`.
5. Go back to Render → your service → **Environment** → update `ALLOWED_ORIGINS` to this Vercel URL → Save.

---

## 5. Load the demo articles (2 min)

1. Open `https://<your-vercel-url>/admin`. Log in with your `ADMIN_PASSWORD`.
2. **Articles** tab → click **Re-embed all**. Wait for the confirmation.

---

## 6. Smoke test (2 min)

1. Open `https://<your-vercel-url>/demo`.
2. Ask: *"How do I reset my password?"* → should get a cited answer.
3. Ask: *"What is the capital of France?"* → should get "I could not find that…".
4. Click **Talk to a human**, fill the form, submit.
5. Go to `/admin` → **Tickets** tab → confirm the ticket is there.

---

## 7. (Optional) Run the real eval

After deploying and loading articles:

```bash
cd api && LLM_PROVIDER=cloudflare .venv/bin/python ../evals/run.py
```

Results are written to `evals/results/latest.json` and `docs/EVALS.md`.

---

## 8. (Optional) Make the repo public

GitHub → repo → **Settings** → **Danger Zone** → **Change visibility** → **Make public**.
Do this only after the CI "Secrets check" job is green.
