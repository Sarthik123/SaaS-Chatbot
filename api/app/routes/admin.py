"""Admin routes: password login and protected management endpoints.

All routes here require the admin to be logged in (checked by _require_admin).
The admin password comes from ADMIN_PASSWORD in the environment.
Authentication uses an httpOnly cookie so the password is not sent on every request.
If ADMIN_PASSWORD is empty, every admin route returns 503 (disabled).
"""

import hashlib
import hmac
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin", tags=["admin"])

# The cookie name. httpOnly means JavaScript cannot read it.
_COOKIE = "admin_session"


# ---------- helpers ----------


def _check_admin_enabled(request: Request) -> None:
    """Raise 503 when ADMIN_PASSWORD is not set (admin area is disabled)."""
    password = request.app.state.settings.admin_password.get_secret_value()
    if not password:
        raise HTTPException(status_code=503, detail="Admin area is not configured.")


def _make_token(password: str, salt: str) -> str:
    """HMAC-SHA256 of the password, keyed by the session secret salt."""
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


def _require_admin(request: Request) -> None:
    """Raise 401 when the request does not carry a valid admin token.

    Accepts the token from either:
    - The X-Admin-Token header (used by the frontend — reliable cross-origin)
    - The admin_session cookie (fallback for local dev / tests)
    """
    _check_admin_enabled(request)
    token = request.headers.get("x-admin-token") or request.cookies.get(_COOKIE, "")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in.")
    password = request.app.state.settings.admin_password.get_secret_value()
    salt = request.app.state.ip_salt
    expected = _make_token(password, salt)
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Not logged in.")


# ---------- login / logout ----------


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def admin_login(body: LoginRequest, request: Request, response: Response):
    """Check the password and set an httpOnly session cookie."""
    _check_admin_enabled(request)
    real_password = request.app.state.settings.admin_password.get_secret_value()
    if not hmac.compare_digest(body.password, real_password):
        raise HTTPException(status_code=401, detail="Wrong password.")
    salt = request.app.state.ip_salt
    token = _make_token(real_password, salt)
    # Cross-origin cookies (Vercel → Render) require samesite="none" + secure=True.
    # Locally / in tests the request is HTTP so we fall back to samesite="lax".
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        samesite="none" if is_https else "lax",
        secure=is_https,
        max_age=86400 * 7,  # 7 days
    )
    # Also return the token in the body so the frontend can store it in localStorage
    # and send it as X-Admin-Token. This is more reliable than cookies cross-origin.
    return {"ok": True, "token": token}


@router.post("/logout")
def admin_logout(request: Request, response: Response):
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    response.delete_cookie(_COOKIE, samesite="none" if is_https else "lax", secure=is_https)
    return {"ok": True}


# ---------- articles ----------


class ArticleIn(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9-]+$")
    source_url: str = Field(default="", max_length=2000)
    body: str = Field(min_length=1)


@router.get("/articles")
def list_articles(request: Request):
    _require_admin(request)
    articles = request.app.state.repository.list_articles()
    return [
        {
            "id": a.id,
            "title": a.title,
            "slug": a.slug,
            "source_url": a.source_url,
            "updated_at": a.updated_at.isoformat(),
        }
        for a in articles
    ]


@router.post("/articles", status_code=201)
def create_article(body: ArticleIn, request: Request):
    """Upload a new article (no chunks yet; call /reindex to embed it)."""
    _require_admin(request)
    article = request.app.state.repository.upsert_article(
        slug=body.slug,
        title=body.title,
        source_url=body.source_url,
        body=body.body,
        chunks=[],
    )
    return {"id": article.id, "slug": article.slug}


@router.delete("/articles/{article_id}", status_code=204)
def delete_article(article_id: int, request: Request):
    _require_admin(request)
    deleted = request.app.state.repository.delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found.")


@router.post("/reindex")
def reindex(request: Request):
    """Re-embed all articles using the current embedding model.

    This is a synchronous, blocking call. It may take a while for large knowledge bases.
    Use with LLM_PROVIDER=fake during testing.
    """
    _require_admin(request)
    from app.rag.ingest import ingest_text

    repo = request.app.state.repository
    embedder = request.app.state.embedder
    articles = repo.list_articles()
    count = 0
    for article in articles:
        ingest_text(
            repo,
            embedder,
            slug=article.slug,
            body=article.body,
            source_url=article.source_url,
            title=article.title,
        )
        count += 1
    return {"reindexed": count}


@router.post("/load-demo")
def load_demo(request: Request):
    """Ingest the bundled demo knowledge base (data/demo_kb/).

    Safe to call multiple times — existing articles are upserted, not duplicated.
    The demo KB is copied into the Docker image at /demo_kb/.
    """
    _require_admin(request)
    import pathlib
    from app.rag.ingest import ingest_text

    # demo_kb/ is bundled inside api/ (copied there so it's always in the Docker build context).
    demo_dir = pathlib.Path(__file__).parents[2] / "demo_kb"
    if not demo_dir.exists():
        raise HTTPException(status_code=404, detail="Demo KB not found on this server.")

    repo = request.app.state.repository
    embedder = request.app.state.embedder
    count = 0
    for md_file in sorted(demo_dir.glob("*.md")):
        body = md_file.read_text(encoding="utf-8")
        lines = body.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else md_file.stem
        slug = md_file.stem
        ingest_text(repo, embedder, slug=slug, body=body, source_url="", title=title)
        count += 1
    return {"loaded": count}


# ---------- conversations ----------


@router.get("/conversations")
def list_conversations(request: Request):
    _require_admin(request)
    convs = request.app.state.repository.list_conversations(limit=50)
    return [
        {"id": c.id, "created_at": c.created_at.isoformat()}
        for c in convs
    ]


# ---------- unanswered ----------


@router.get("/unanswered")
def list_unanswered(request: Request):
    _require_admin(request)
    msgs = request.app.state.repository.list_unanswered(limit=50)
    return [
        {
            "message_id": m.id,
            "conversation_id": m.conversation_id,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]


# ---------- tickets ----------


@router.get("/tickets")
def list_tickets(request: Request, status: str | None = None):
    _require_admin(request)
    if status and status not in ("open", "closed"):
        raise HTTPException(status_code=422, detail="status must be 'open' or 'closed'")
    _require_admin(request)
    tickets = request.app.state.repository.list_tickets(status=status)
    return [
        {
            "id": t.id,
            "conversation_id": t.conversation_id,
            "name": t.name,
            "email": t.email,
            "message": t.message,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in tickets
    ]


# ---------- stats ----------


@router.get("/stats")
def get_stats(request: Request):
    _require_admin(request)
    return request.app.state.repository.get_stats()
