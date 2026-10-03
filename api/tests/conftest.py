"""Shared test setup.

Tests must never depend on whatever happens to be in your shell or in your .env file,
so every test starts with the app's environment variables removed.
"""

import pytest

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
