-- Postgres bootstrap script.
-- Runs once on first container start via /docker-entrypoint-initdb.d/.
-- Owns extensions and database-level grants only. All table DDL lives in Alembic
-- (apps/api/alembic/versions/) so there is one and only one source of truth for schema.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

GRANT ALL PRIVILEGES ON SCHEMA public TO depart_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO depart_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO depart_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO depart_user;
