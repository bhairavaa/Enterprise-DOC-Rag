-- Extensions required by application schema (UUID generation, etc.)
-- Table creation itself is owned by Alembic migrations (backend/alembic/versions).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
