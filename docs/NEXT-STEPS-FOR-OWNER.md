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

## Check Phase 2: the AI brain (15 minutes with a Cloudflare account)

You need the Phase 1 local database running and the fake articles ingested first.

1. Follow "Cloudflare account and token" below to get `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.
2. Add them to your `.env` file:
   ```
   CLOUDFLARE_ACCOUNT_ID=your-account-id
   CLOUDFLARE_API_TOKEN=your-token
   LLM_PROVIDER=cloudflare
   LLM_MODEL=@cf/mistral/mistral-7b-instruct-v0.1
   EMBEDDING_MODEL=@cf/baai/bge-base-en-v1.5
   EMBEDDING_DIM=768
   ```
3. Re-ingest the demo articles so they get real embeddings:
   `python -m app.rag.ingest ../data/demo_kb`
4. Ask the bot a question:
   `python -m app.cli ask --demo "how do I reset my password?"`
   You should see a short cited answer, not the fallback message.
5. Ask something not in the articles:
   `python -m app.cli ask --demo "what is the capital of France?"`
   You should see: "I could not find that in our help articles…"

## Cloudflare account and token (free, about 20 minutes)

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) and sign up for a free account.
2. After logging in, look at the URL: `dash.cloudflare.com/<your-account-id>`. Copy that id —
   it is about 32 characters. This is `CLOUDFLARE_ACCOUNT_ID`.
3. In the left sidebar click **AI** to confirm Workers AI is available on your account.
4. Click your account name (top right) → **Profile** → **API Tokens** → **Create Token**.
5. Choose **Create Custom Token**. Give it a name like "SaaS Chatbot".
6. Under "Permissions" add: **Account** → **Workers AI** → **Edit**.
7. Click **Continue to summary** → **Create Token**.
8. Copy the token immediately (it is only shown once). This is `CLOUDFLARE_API_TOKEN`.
9. Paste both into your `.env` file as shown in the Phase 2 check above.

## Accounts you will need later (do these when you want to run with real AI, about 1 to 2 hours)

| Account | Needed from | Where it goes |
|---|---|---|
| Neon (free Postgres) | Phase 1 live check and Phase 7 | `DATABASE_URL` |
| Cloudflare (free Workers AI): Account ID and an API token that allows Workers AI | Phase 2 real answers | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| Vercel and Render (free) | Phase 7 | their "Environment variables" screens |

Exact click-by-click steps for each are added to this file in the phase that needs them.

## Phase 7: Deploy to the internet (1–2 hours the first time)

You need four free accounts: **Neon** (database), **Cloudflare** (AI models), **Render** (API server), **Vercel** (website). Steps are in this order because each one's output is needed by the next.

### A. Create the database on Neon (10 minutes)

1. Go to [neon.tech](https://neon.tech) and sign up for a free account.
2. Click **New project**. Name it `saas-chatbot`. Leave the region as the default.
3. On the project dashboard, find the **Connection string** box. Click **Copy**.
   It looks like: `postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`
   This is your `DATABASE_URL`. Save it somewhere safe — you will need it in steps B and C.
4. In the Neon dashboard, click **SQL editor** and run this one command to enable the vector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
5. Click **Run** and confirm you see "Success".

### B. Get Cloudflare Workers AI keys (follow the "Cloudflare account and token" section above)

You should already have `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` from Phase 2.
If not, follow the "Cloudflare account and token" section above now. Keep them ready.

### C. Deploy the API on Render (20 minutes)

1. Go to [render.com](https://render.com) and sign up with your GitHub account.
2. Click **New** → **Web Service**.
3. Connect your GitHub account if prompted, then find and select the `SaaS-Chatbot` repository.
4. Fill in the settings exactly as follows:
   - **Name**: `saas-chatbot-api`
   - **Root directory**: _(leave blank — the Dockerfile path handles this)_
   - **Runtime**: Docker
   - **Dockerfile path**: `api/Dockerfile`
   - **Instance type**: Free
5. Scroll down to **Environment Variables** and add all of these (click **Add environment variable** for each):
   ```
   DATABASE_URL        = (paste the Neon connection string from step A.3)
   CLOUDFLARE_ACCOUNT_ID = (from step B)
   CLOUDFLARE_API_TOKEN  = (from step B)
   LLM_PROVIDER        = cloudflare
   LLM_MODEL           = @cf/mistral/mistral-7b-instruct-v0.1
   EMBEDDING_MODEL     = @cf/baai/bge-base-en-v1.5
   EMBEDDING_DIM       = 768
   ADMIN_PASSWORD      = (choose any strong password — write it down)
   SESSION_SECRET      = (type 32 random characters, e.g. use a password manager)
   ALLOWED_ORIGINS     = https://saas-chatbot.vercel.app
   ```
   _(You will update `ALLOWED_ORIGINS` in step D.5 once you know the real Vercel URL.)_
6. Click **Create Web Service**. Render will build the Docker image (3–5 minutes).
7. Wait for the deploy log to show `Application startup complete.`
8. Copy the URL Render gives you — it looks like `https://saas-chatbot-api.onrender.com`. This is your `NEXT_PUBLIC_API_URL`.

### D. Deploy the website on Vercel (10 minutes)

1. Go to [vercel.com](https://vercel.com) and sign up with your GitHub account.
2. Click **Add New Project** → find `SaaS-Chatbot` → click **Import**.
3. Vercel will auto-detect Next.js. In the **Root Directory** box type: `web`
4. Under **Environment Variables** add:
   ```
   NEXT_PUBLIC_API_URL = (paste the Render URL from step C.8, e.g. https://saas-chatbot-api.onrender.com)
   ```
5. Click **Deploy**. Wait for the green tick (1–3 minutes).
6. Vercel shows your live URL, e.g. `https://saas-chatbot.vercel.app`.
7. Go back to the Render dashboard → your service → **Environment** tab. Update `ALLOWED_ORIGINS` to the real Vercel URL. Click **Save Changes** — Render redeploys automatically.

### E. Ingest the demo articles into the live database (5 minutes)

1. Open your Vercel URL and go to `/admin` (e.g. `https://saas-chatbot.vercel.app/admin`).
2. Log in with the `ADMIN_PASSWORD` you set in step C.5.
3. Click the **Articles** tab → **Re-embed all** button.
4. Wait for the confirmation message. The 25 demo articles are now in Neon with real embeddings.

### F. Verify everything works (5 minutes)

1. Go to `https://saas-chatbot.vercel.app/demo` and click the chat bubble.
2. Ask: "How do I reset my password?" — you should see a cited answer.
3. Ask: "What is the capital of France?" — you should see the "I don't know" fallback.
4. Click "Talk to a human", fill in the form, submit.
5. Go back to `/admin` → **Tickets** tab and confirm the ticket is there.
6. Check `/admin` → **Stats** tab for counts.

### G. (Optional) Make the repository public

When you want recruiters to read the code: GitHub → repo → **Settings** → scroll to **Danger Zone** → **Change visibility** → **Make public**.
Do this only after the CI "Secrets check" job passes (it scans every commit for leaked keys).

---

## Optional: make the repository public

The guide says a public repo is fine because secrets never go into it. When you want recruiters to
read the code: GitHub, repo **Settings**, scroll to **Danger Zone**, **Change visibility**,
**Make public**. Do this only after the secrets check (added in Phase 7) passes.
