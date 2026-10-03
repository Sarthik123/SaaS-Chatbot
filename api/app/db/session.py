"""Creating the database connection (an "engine")."""

from sqlalchemy import Engine, create_engine


def normalize_database_url(url: str) -> str:
    """Make a connection string work with the psycopg 3 driver we use.

    Neon (and most hosts) hand out strings starting with `postgresql://` or `postgres://`.
    SQLAlchemy needs `postgresql+psycopg://` to pick the psycopg 3 driver.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(database_url: str, **connect_args) -> Engine:
    """Open a connection pool to Postgres.

    * pool_pre_ping: test a connection before using it (free-tier databases close idle ones).
    * prepare_threshold=None: do not use "prepared statements". Neon's pooled connection
      string goes through PgBouncer, which does not support them.
    """
    return create_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None, **connect_args},
    )
