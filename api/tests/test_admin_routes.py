"""Tests for feedback, handoff, and admin routes (Phase 3).

All tests use InMemoryRepository and fake providers.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.memory import InMemoryRepository
from app.db.repository import NewChunk
from app.main import create_app
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider

DIM = 64
ADMIN_PASSWORD = "test-admin-password"


def _embedding(text: str) -> list[float]:
    return FakeEmbeddingProvider(dim=DIM).embed([text])[0]


def make_client(*, admin_password: str = ADMIN_PASSWORD) -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository(DIM)
    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        embedding_dim=DIM,
        admin_password=admin_password,
        session_secret="test-session-secret",
        min_similarity=0.0,
    )
    app = create_app(
        settings,
        repository=repo,
        embedder=FakeEmbeddingProvider(dim=DIM),
        llm=FakeLLMProvider(),
    )
    return TestClient(app), repo


def add_article(repo):
    repo.upsert_article(
        slug="help",
        title="Help",
        source_url="https://help.example/help",
        body="Open Settings and choose Reset.",
        chunks=[
            NewChunk(
                chunk_index=0,
                heading="Help",
                text="Open Settings and choose Reset.",
                token_count=6,
                embedding=_embedding("Open Settings and choose Reset."),
            )
        ],
    )


def chat_and_get_message_id(client) -> tuple[str, str]:
    """Send one chat message and return (conversation_id, message_id) of the assistant reply."""
    response = client.post("/api/chat", json={"message": "how do I reset"})
    assert response.status_code == 200
    body = response.json()
    return body["conversation_id"], body["message_id"]


# ========== POST /api/feedback ==========


def test_feedback_201_for_thumbs_up():
    client, repo = make_client()
    add_article(repo)
    _, message_id = chat_and_get_message_id(client)
    response = client.post("/api/feedback", json={"message_id": message_id, "rating": "up"})
    assert response.status_code == 200
    assert "feedback_id" in response.json()


def test_feedback_201_for_thumbs_down_with_comment():
    client, repo = make_client()
    add_article(repo)
    _, message_id = chat_and_get_message_id(client)
    response = client.post(
        "/api/feedback",
        json={"message_id": message_id, "rating": "down", "comment": "not helpful"},
    )
    assert response.status_code == 200


def test_feedback_422_for_unknown_message_id():
    client, _ = make_client()
    response = client.post(
        "/api/feedback",
        json={"message_id": "00000000-0000-0000-0000-000000000000", "rating": "up"},
    )
    assert response.status_code == 422


def test_feedback_422_for_invalid_rating():
    client, repo = make_client()
    add_article(repo)
    _, message_id = chat_and_get_message_id(client)
    response = client.post(
        "/api/feedback", json={"message_id": message_id, "rating": "meh"}
    )
    assert response.status_code == 422


# ========== POST /api/handoff ==========


def test_handoff_creates_ticket():
    client, repo = make_client()
    add_article(repo)
    conv_id, _ = chat_and_get_message_id(client)
    response = client.post(
        "/api/handoff",
        json={
            "conversation_id": conv_id,
            "name": "Alice",
            "email": "alice@example.com",
            "message": "I need help with billing.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "ticket_id" in body
    assert body["ticket_id"] > 0


def test_handoff_works_without_conversation_id():
    client, _ = make_client()
    response = client.post(
        "/api/handoff",
        json={"name": "Bob", "email": "bob@example.com", "message": "Need help."},
    )
    assert response.status_code == 200


def test_handoff_422_for_invalid_email():
    client, _ = make_client()
    response = client.post(
        "/api/handoff",
        json={"name": "Eve", "email": "not-an-email", "message": "help"},
    )
    assert response.status_code == 422


def test_handoff_422_for_missing_name():
    client, _ = make_client()
    response = client.post(
        "/api/handoff",
        json={"email": "x@example.com", "message": "help"},
    )
    assert response.status_code == 422


# ========== Admin auth ==========


def _login(client, password=ADMIN_PASSWORD):
    return client.post("/api/admin/login", json={"password": password})


def test_admin_login_succeeds_with_correct_password():
    client, _ = make_client()
    response = _login(client)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_admin_login_sets_a_cookie():
    client, _ = make_client()
    response = _login(client)
    assert "admin_session" in response.cookies


def test_admin_login_fails_with_wrong_password():
    client, _ = make_client()
    response = client.post("/api/admin/login", json={"password": "wrong"})
    assert response.status_code == 401


def test_admin_endpoints_return_401_without_login():
    client, _ = make_client()
    for path in ["/api/admin/articles", "/api/admin/conversations", "/api/admin/stats"]:
        response = client.get(path)
        assert response.status_code == 401, f"{path} should be 401 without login"


def test_admin_503_when_password_not_configured():
    client, _ = make_client(admin_password="")
    response = client.post("/api/admin/login", json={"password": ""})
    assert response.status_code == 503


# ========== Admin: articles ==========


def test_admin_list_articles_after_login():
    client, repo = make_client()
    add_article(repo)
    _login(client)
    response = client.get("/api/admin/articles")
    assert response.status_code == 200
    articles = response.json()
    assert len(articles) == 1
    assert articles[0]["slug"] == "help"


def test_admin_create_article():
    client, _ = make_client()
    _login(client)
    response = client.post(
        "/api/admin/articles",
        json={
            "title": "Test Article",
            "slug": "test-article",
            "source_url": "https://help.example/test",
            "body": "# Test\n\nSome content here.",
        },
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "test-article"


def test_admin_delete_article():
    client, repo = make_client()
    add_article(repo)
    _login(client)
    articles = client.get("/api/admin/articles").json()
    article_id = articles[0]["id"]
    response = client.delete(f"/api/admin/articles/{article_id}")
    assert response.status_code == 204
    assert client.get("/api/admin/articles").json() == []


def test_admin_delete_unknown_article_is_404():
    client, _ = make_client()
    _login(client)
    response = client.delete("/api/admin/articles/99999")
    assert response.status_code == 404


# ========== Admin: conversations ==========


def test_admin_conversations_returns_list():
    client, repo = make_client()
    add_article(repo)
    chat_and_get_message_id(client)
    _login(client)
    convs = client.get("/api/admin/conversations").json()
    assert len(convs) >= 1
    assert "id" in convs[0]


# ========== Admin: unanswered ==========


def test_admin_unanswered_includes_abstained_replies():
    client, _ = make_client()  # empty repo = always abstains
    client.post("/api/chat", json={"message": "what is 2+2"})
    _login(client)
    unanswered = client.get("/api/admin/unanswered").json()
    assert len(unanswered) >= 1


# ========== Admin: tickets ==========


def test_admin_tickets_returns_submitted_handoffs():
    client, _ = make_client()
    client.post(
        "/api/handoff",
        json={"name": "Carol", "email": "carol@example.com", "message": "help"},
    )
    _login(client)
    tickets = client.get("/api/admin/tickets").json()
    assert len(tickets) == 1
    assert tickets[0]["name"] == "Carol"
    assert tickets[0]["status"] == "open"


def test_admin_tickets_filter_by_status():
    client, _ = make_client()
    client.post(
        "/api/handoff",
        json={"name": "Dan", "email": "dan@example.com", "message": "help"},
    )
    _login(client)
    open_tickets = client.get("/api/admin/tickets?status=open").json()
    assert len(open_tickets) == 1
    closed_tickets = client.get("/api/admin/tickets?status=closed").json()
    assert len(closed_tickets) == 0


# ========== Admin: stats ==========


def test_admin_stats_returns_expected_keys():
    client, repo = make_client()
    add_article(repo)
    chat_and_get_message_id(client)
    _login(client)
    stats = client.get("/api/admin/stats").json()
    expected_keys = {
        "total_conversations",
        "total_messages",
        "abstain_rate",
        "thumbs_up",
        "thumbs_down",
        "total_open_tickets",
    }
    assert expected_keys <= set(stats.keys())


def test_admin_stats_total_messages_is_nonzero_after_chat():
    client, repo = make_client()
    add_article(repo)
    chat_and_get_message_id(client)
    _login(client)
    stats = client.get("/api/admin/stats").json()
    assert stats["total_messages"] >= 2  # user message + assistant message


# ========== Admin: reindex ==========


def test_admin_reindex_runs_without_error():
    client, repo = make_client()
    # Upload an article body and reindex it using the fake embedder.
    _login(client)
    client.post(
        "/api/admin/articles",
        json={
            "title": "Reindex Test",
            "slug": "reindex-test",
            "source_url": "https://x",
            "body": "# Reindex\n\nSome text to embed.",
        },
    )
    response = client.post("/api/admin/reindex")
    assert response.status_code == 200
    assert response.json()["reindexed"] == 1
