"""The FastAPI application. Start it with:  uvicorn app.main:app --reload  (from api/)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.routes import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; normal runs read the environment."""
    settings = settings or get_settings()

    app = FastAPI(title="SaaS AI Support Agent API")
    app.state.settings = settings

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
    return app


app = create_app()
