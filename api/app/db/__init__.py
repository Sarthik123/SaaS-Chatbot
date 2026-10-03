"""Database code: tables (models.py), the storage contract (repository.py) and its two versions."""

from app.config import Settings
from app.db.memory import InMemoryRepository
from app.db.postgres import PostgresRepository
from app.db.repository import Repository
from app.db.session import make_engine


def build_repository(settings: Settings) -> Repository:
    """Postgres when DATABASE_URL is set, otherwise a throw-away in-memory fake.

    The in-memory fake forgets everything when the program stops. It is meant for tests and
    quick local experiments only; real deployments always set DATABASE_URL.
    """
    database_url = settings.database_url.get_secret_value()
    if database_url:
        return PostgresRepository(make_engine(database_url), settings.embedding_dim)
    return InMemoryRepository(settings.embedding_dim)


__all__ = ["InMemoryRepository", "PostgresRepository", "Repository", "build_repository"]
