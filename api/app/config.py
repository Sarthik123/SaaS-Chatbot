"""Settings for the whole backend.

Every setting comes from an environment variable (or from the .env file in the
repo root, which is never uploaded to GitHub). Nothing secret is ever written in code.

Two beginner-friendly rules are built in:
  * The app must START even when keys are empty. Missing keys only cause an error
    later, at the moment a real AI call is attempted.
  * An empty value (for example `EMBEDDING_DIM=` copied from .env.example) is treated
    as "not set", so the default below is used instead of crashing.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# api/app/config.py -> parents[2] is the repo root, wherever you start the server from.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # empty value means "not set" -> use the default
        extra="ignore",  # the shared .env may hold names only the website uses
    )

    # --- Secrets. SecretStr hides the value if the settings are ever printed or logged.
    database_url: SecretStr = SecretStr("")
    cloudflare_api_token: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    admin_password: SecretStr = SecretStr("")  # empty means the admin area is disabled
    session_secret: SecretStr = SecretStr("")

    # --- Not secret.
    cloudflare_account_id: str = ""
    # Which AI provider to use. "fake" is for tests: no internet, no cost.
    llm_provider: Literal["cloudflare", "openai", "fake"] = "cloudflare"
    # Empty model names mean "use the provider's default" (see docs/DECISIONS.md D20/D21).
    # For OpenAI there is no default: set both names yourself.
    llm_model: str = ""
    embedding_model: str = ""
    # Size of an embedding vector. It MUST match the embedding model. 768 matches the default
    # Cloudflare model (@cf/baai/bge-base-en-v1.5). If you change the model, change this too and
    # recreate the database tables (the size is fixed when the migration runs).
    embedding_dim: int = 768
    # Browser addresses allowed to call the API, separated by commas.
    allowed_origins: str = "http://localhost:3000"

    # --- How the bot decides (AGENTS.md "RAG rules").
    # Tune these with the eval set, not by guessing.
    # A chunk must be at least this similar (cosine, 0 to 1) to the question to be used. If no
    # chunk passes, the bot says "I don't know" WITHOUT calling the AI model.
    min_similarity: float = 0.35
    # The most words-pieces ("tokens") the AI model may write in one answer.
    max_output_tokens: int = 400

    # --- Limits and safety.
    # Messages allowed per visitor (per IP address) in each time window.
    rate_limit_messages: int = 20
    rate_limit_window_seconds: int = 600
    # Behind a proxy such as Render the real visitor address is in the X-Forwarded-For header.
    # Only turn this on when the API really is behind a proxy you trust; otherwise anyone could
    # fake the header and dodge the rate limit.
    trust_proxy_headers: bool = False
    # Seconds to wait for the AI provider before giving up.
    provider_timeout_seconds: float = 30.0

    @property
    def allowed_origins_list(self) -> list[str]:
        """ALLOWED_ORIGINS as a clean list (no spaces, no trailing slashes)."""
        parts = (item.strip().rstrip("/") for item in self.allowed_origins.split(","))
        return [item for item in parts if item]


@lru_cache
def get_settings() -> Settings:
    """Read the settings once and reuse them."""
    return Settings()
