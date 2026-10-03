import pytest
from pydantic import ValidationError

from app.config import Settings


def load(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_defaults_when_nothing_is_set():
    settings = load()
    assert settings.llm_provider == "cloudflare"
    assert settings.embedding_dim == 384
    assert settings.allowed_origins_list == ["http://localhost:3000"]
    assert settings.admin_password.get_secret_value() == ""  # admin area disabled by default


def test_values_are_read_from_environment_variables(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_DIM", "768")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")
    settings = load()
    assert settings.llm_provider == "openai"
    assert settings.embedding_dim == 768
    assert settings.cloudflare_account_id == "acct-123"


def test_empty_values_fall_back_to_defaults(monkeypatch):
    # .env.example has lines like `EMBEDDING_DIM=` - they must not crash the app.
    monkeypatch.setenv("EMBEDDING_DIM", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    settings = load()
    assert settings.embedding_dim == 384
    assert settings.llm_provider == "cloudflare"


def test_empty_values_in_an_env_file_also_fall_back(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("EMBEDDING_DIM=\nLLM_MODEL=my-model\n")
    settings = Settings(_env_file=env_file)
    assert settings.embedding_dim == 384
    assert settings.llm_model == "my-model"


def test_allowed_origins_are_split_and_cleaned():
    settings = load(allowed_origins=" https://a.example/ , https://b.example ,, ")
    assert settings.allowed_origins_list == ["https://a.example", "https://b.example"]


def test_unknown_provider_is_rejected_with_a_clear_error():
    with pytest.raises(ValidationError):
        load(llm_provider="made-up")


def test_secrets_are_hidden_when_settings_are_printed():
    settings = load(
        cloudflare_api_token="super-secret-token",
        openai_api_key="sk-secret",
        database_url="postgresql://user:pw@host/db",
        admin_password="pw-secret",
        session_secret="session-secret",
    )
    shown = repr(settings) + str(settings)
    for secret in ["super-secret-token", "sk-secret", "pw@host", "pw-secret", "session-secret"]:
        assert secret not in shown
