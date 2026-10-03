"""Alembic's entry point: decides which database to change and runs the migration steps."""

from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.db.models import Base
from app.db.session import make_engine, normalize_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # Tests can set sqlalchemy.url on the config; normal use reads DATABASE_URL from the
    # environment / .env file.
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url.get_secret_value()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env, set DATABASE_URL, and try again."
        )
    return url


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (alembic upgrade head --sql)."""
    context.configure(
        url=normalize_database_url(_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass an already-open connection (so they can use a private schema).
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine(_database_url())
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
