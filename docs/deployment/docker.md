# Docker & Compose Deployment

The repository ships a `Dockerfile`, `.dockerignore` and `docker-compose.yml` at the
root. The image is a single stage on `python:3.12-slim`, installs ArcHub with the
`server` + `postgres` extras, runs as a **non-root** user (`uid 10001`), persists data
in a `/data` volume, and includes a container `HEALTHCHECK`.

## Quick start — app only (SQLite)

```bash
docker compose up --build
```

Then open:

| URL | What |
|---|---|
| `http://127.0.0.1:8088/admin/archub` | CMS backoffice |
| `http://127.0.0.1:8088/admin/itsm` | ITSM Service Desk |
| `http://127.0.0.1:8088/admin/itsm/workflow` | Offline BPMN editor |
| `http://127.0.0.1:8088/api/docs` | OpenAPI |

Data (SQLite DB + runtime exports) lives in the named volume `archub-data`, so it
survives `docker compose down` / `up`. Remove it with `docker compose down -v`.

## With PostgreSQL for the ITSM plugin

A Compose **profile** starts a PostgreSQL service alongside the app:

```bash
docker compose --profile itsm-postgres up --build
```

Then point the ITSM plugin at it by uncommenting the env var in `docker-compose.yml`
(or set it inline):

```yaml
services:
  archub:
    environment:
      ARCHUB_ITSM_PG_DSN: postgresql://archub:archub@postgres:5432/archub_itsm
```

The plugin's request store **and** all ITIL reference data (catalog, SLA, CMDB,
persisted BPMN schemes) then live in PostgreSQL; the rest of the CMS stays on SQLite.
The Postgres tables are created automatically on first use.

## Run with plain `docker` (no Compose)

```bash
docker build -t archub-platform:local .

docker run --rm -p 8088:8000 \
  -e ARCHUB_BACKGROUND_JOBS=true \
  -v archub-data:/data \
  archub-platform:local
```

## The Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARCHUB_CMS_DB=/data/archub_cms.db \
    ARCHUB_RUNTIME_EXPORT_DIR=/data/archub_runtime \
    ARCHUB_PLUGIN_DIRS=/app/plugins

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY plugins ./plugins
RUN python -m pip install --upgrade pip && python -m pip install ".[server,postgres]"

RUN useradd --create-home --uid 10001 archub && mkdir -p /data && chown -R archub:archub /data /app
USER archub
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "archub_cms.app:create_archub_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

## Environment

The container honours every variable in [Configuration](../reference/configuration.md).
The image presets sensible container defaults:

| Variable | Image default | Note |
|---|---|---|
| `ARCHUB_CMS_DB` | `/data/archub_cms.db` | on the persistent volume |
| `ARCHUB_RUNTIME_EXPORT_DIR` | `/data/archub_runtime` | on the persistent volume |
| `ARCHUB_PLUGIN_DIRS` | `/app/plugins` | bundled plugin manifests |

## Production hardening

- Put a TLS-terminating reverse proxy (Traefik/nginx/Caddy) in front; the app speaks
  plain HTTP on `:8000`.
- Build a release tag instead of `:local`, and pin the base image by digest.
- For multiple replicas, use `ARCHUB_ITSM_PG_DSN` (shared Postgres) and an external
  database for the CMS rather than the per-container SQLite volume.
- Disable demo seeding for a clean instance by running the app factory with
  `seed_demo=False` (e.g. a thin wrapper module) — see [Local Deployment](local.md).
- The built-in `HEALTHCHECK` probes `/api/docs`; wire it to your orchestrator's
  readiness checks.
