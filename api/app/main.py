"""The FastAPI application. Start it with:  uvicorn app.main:app --reload  (from api/)."""

import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.db import Repository, build_repository
from app.providers import (
    EmbeddingProvider,
    LLMProvider,
    build_embedding_provider,
    build_llm_provider,
)
from app.routes import admin, chat, feedback, handoff, health
from app.security import RateLimiter


def create_app(
    settings: Settings | None = None,
    *,
    repository: Repository | None = None,
    embedder: EmbeddingProvider | None = None,
    llm: LLMProvider | None = None,
) -> FastAPI:
    """Build the app.

    Normal runs read everything from the environment. Tests pass their own settings and fakes
    (a fake repository and fake AI providers), so they need no database and cost nothing.
    """
    settings = settings or get_settings()

    app = FastAPI(title="SaaS AI Support Agent API")
    app.state.settings = settings
    app.state.repository = repository or build_repository(settings)
    app.state.embedder = embedder or build_embedding_provider(settings)
    app.state.llm = llm or build_llm_provider(settings)
    app.state.rate_limiter = RateLimiter(
        settings.rate_limit_messages, settings.rate_limit_window_seconds
    )
    # Salt for the one-way visitor fingerprint. If SESSION_SECRET is not set we use a random
    # value that lasts until the process restarts (so nothing stable can be traced back).
    app.state.ip_salt = settings.session_secret.get_secret_value() or secrets.token_hex(16)

    # CORS: the browser only lets our website call this API if its address is listed here.
    # We never use "*" because later the admin login uses a cookie.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    app.include_router(handoff.router)
    app.include_router(admin.router)
    return app


app = create_app()
