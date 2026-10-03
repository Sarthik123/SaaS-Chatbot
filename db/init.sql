-- Runs once when the local Postgres container is first created (see docker-compose.yml).
-- pgvector adds the "vector" column type and nearest-neighbour search.
-- The Alembic migration in Phase 1 also runs this statement, so it is safe to run twice.
CREATE EXTENSION IF NOT EXISTS vector;
