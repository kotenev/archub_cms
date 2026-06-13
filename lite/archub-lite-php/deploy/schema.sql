-- ArcHub Lite — PostgreSQL schema.
--
-- The application creates this automatically on first request (see
-- src/Infrastructure/Migrator.php). Run it by hand only if your host disallows
-- DDL from the app role:
--
--   psql "$DATABASE_URL" -f deploy/schema.sql
--
-- Requires PostgreSQL 12+ (generated columns).

CREATE TABLE IF NOT EXISTS archub_lite_pages (
    id           BIGSERIAL PRIMARY KEY,
    slug         TEXT NOT NULL UNIQUE,
    parent_id    BIGINT REFERENCES archub_lite_pages(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'draft',
    sort         INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    tsv          tsvector GENERATED ALWAYS AS (
                     to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, ''))
                 ) STORED
);

CREATE INDEX IF NOT EXISTS archub_lite_pages_tsv_idx    ON archub_lite_pages USING GIN (tsv);
CREATE INDEX IF NOT EXISTS archub_lite_pages_parent_idx ON archub_lite_pages (parent_id);
CREATE INDEX IF NOT EXISTS archub_lite_pages_status_idx ON archub_lite_pages (status);

CREATE TABLE IF NOT EXISTS archub_lite_requests (
    id          BIGSERIAL PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    type        TEXT NOT NULL DEFAULT 'incident',
    summary     TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',
    priority    TEXT NOT NULL DEFAULT 'medium',
    requester   TEXT NOT NULL DEFAULT 'anonymous',
    assignee    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS archub_lite_requests_status_idx ON archub_lite_requests (status);
