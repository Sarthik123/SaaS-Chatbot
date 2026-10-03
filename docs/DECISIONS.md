# Decisions

Every choice the AI coding tool made on the owner's behalf, with the alternatives and the reason.
The owner can overrule any of these; change the entry when that happens.

| # | Phase | Decision | Alternatives considered | Why |
|---|---|---|---|---|
| D1 | 0 | Use **Claude Code** (an AI coding tool by Anthropic) to write the code. The owner's `AGENTS.md` is the rulebook; `CLAUDE.md` contains one line, `@AGENTS.md`, so Claude Code reads the same rules. | OpenAI Codex | The owner's resume names Claude for this project. One tool per phase, commit before switching. |
| D2 | 0 | Keep the GitHub repository the owner actually created, `Sarthik123/SaaS-Chatbot` (private for now), instead of the guide's example name `saas-ai-support-agent`. | Create a second repo with the guide's name | The owner already created and connected this repo. A second repo would split the history. The guide says public is fine because no secrets are committed; making it public is the owner's choice (see NEXT-STEPS-FOR-OWNER.md). |
| D3 | 0 | Backend Python target is 3.11+. CI runs Python 3.12; the build environment used 3.13. | Pin one version | The guide asks for 3.11+. Running two versions in practice shows nothing is version-fragile. |
| D4 | 0 | The backend settings treat an **empty** environment value as "not set" and use the default. | Crash on empty values | `.env.example` ships with empty values; copying it must not break the app. The app must start even when keys are empty. |
| D5 | 0 | Secrets are stored as `SecretStr` in settings so printing the settings never shows them. | Plain strings | Prevents accidental leaks in logs. Covered by a test. |
| D6 | 0 | The test client uses `httpx2`, which the installed FastAPI/Starlette versions require for `TestClient`. | `httpx` | The packages installed in this environment recommend it. Used only in tests. |
| D7 | 0 | Website uses system fonts (no Google Fonts download). | Next.js Google fonts | Builds work offline and in CI; pages load faster. |
| D8 | 0 | Placeholder embedding size `EMBEDDING_DIM=384` until Phase 2. | Choose the real model now | Phase 2 is when the real embedding model is chosen from the provider's current list; the size must match it then. |
