"""Shared test setup.

Tests must never depend on whatever happens to be in your shell or in your .env file,
so every test starts with the app's environment variables removed.

The one exception: the few "integration" tests that need a real Postgres. They read the
database address that was in the environment when pytest started (REAL_DATABASE_URL) and are
skipped when there was none. They only ever create and delete their own private schema, so
they never touch real tables.
"""

import os

import pytest

from app.config import get_settings

# Captured at import time, BEFORE the fixture below removes DATABASE_URL from each test.
REAL_DATABASE_URL = os.environ.get("DATABASE_URL", "")

SETTING_NAMES = [
    "DATABASE_URL",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "OPENAI_API_KEY",
    "ADMIN_PASSWORD",
    "SESSION_SECRET",
    "ALLOWED_ORIGINS",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    # get_settings() remembers its answer. Importing app.main (at collection time) may have
    # remembered settings read from the real environment, so forget them for every test.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
