from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(**settings) -> TestClient:
    # _env_file=None: ignore any real .env file so the test is repeatable anywhere.
    return TestClient(create_app(Settings(_env_file=None, **settings)))


def test_health_returns_ok():
    response = make_client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_starts_with_every_key_empty():
    # No keys, no database: the app must still start and answer.
    assert make_client().get("/api/health").status_code == 200


def test_cors_allows_the_configured_website():
    client = make_client(allowed_origins="https://my-site.example")
    response = client.get("/api/health", headers={"Origin": "https://my-site.example"})
    assert response.headers.get("access-control-allow-origin") == "https://my-site.example"


def test_cors_blocks_other_websites():
    client = make_client(allowed_origins="https://my-site.example")
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
