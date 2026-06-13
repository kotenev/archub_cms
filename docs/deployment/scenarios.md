# Deployment Scenarios

ArcHub is a single Apache-2.0 Python package with **zero required services** by default —
embedded SQLite and an offline LLM. PostgreSQL and an online LLM are optional upgrades.
This page maps the **deployment shapes** from a laptop to a clustered, PostgreSQL-backed
install, and links to the step-by-step guides.

| Scenario | Storage | AI | Concurrency | Guide |
|---|---|---|---|---|
| [1. Embedded library](#1-embedded-in-a-fastapi-app) | host's choice | host's choice | host's | [Local](local.md#4-embed-in-an-existing-fastapi-app) |
| [2. Standalone single node](#2-standalone-single-node) | SQLite | offline | single process | [Local](local.md) |
| [3. Container](#3-container-docker-compose) | SQLite volume | offline/online | single replica | [Docker](docker.md) |
| [4. PostgreSQL + multi-replica](#4-postgresql-multi-replica) | PostgreSQL | online | many replicas | [Docker](docker.md) |
| [5. Air-gapped / offline](#5-air-gapped-offline) | SQLite/PG | **offline only** | any | below |
| [6. Online LLM upgrade](#6-online-llm-upgrade) | any | online + breaker | any | [Config](../reference/configuration.md) |

---

## 1. Embedded in a FastAPI app

The lightest footprint: ArcHub is a set of routers inside *your* application. You own the
server, auth and lifecycle; ArcHub contributes the CMS, knowledge and/or ITSM surfaces.

```python
from fastapi import FastAPI
from archub_cms.web.routes import router as archub_router
from archub_cms.web.platform_routes import platform_router
from archub_cms.web.itsm_routes import itsm_router, itsm_web_router

app = FastAPI()
app.include_router(archub_router)     # public delivery + CMS backoffice
app.include_router(platform_router)   # /api/platform/* (knowledge, plugins)
app.include_router(itsm_router)       # /api/platform/itsm/* (optional)
app.include_router(itsm_web_router)   # /admin/itsm + workflow editor (optional)
```

Host concerns (auth, templates, cache invalidation, audit, LLM) are **Protocol ports** —
implement them against your existing infrastructure. Mount only what you need.

**Best for:** adding docs / help center / ticketing to an existing Python product.

---

## 2. Standalone single node

The batteries-included app, no container. One process, embedded SQLite, offline AI — a
laptop with Python is enough.

```bash
python -m pip install -e ".[server]"
uvicorn archub_cms.app:create_archub_app --factory --host 0.0.0.0 --port 8088
```

For production, front it with a process manager and a reverse proxy:

```bash
gunicorn -k uvicorn.workers.UvicornWorker 'archub_cms.app:create_archub_app'
```

```python
# Skip demo seeding for a clean instance:
from archub_cms.app import create_archub_app
app = create_archub_app(seed_demo=False)
```

Persist data outside the repo:

```bash
export ARCHUB_CMS_DB=/var/lib/archub/archub_cms.db
export ARCHUB_RUNTIME_EXPORT_DIR=/var/lib/archub/runtime
export ARCHUB_BACKGROUND_JOBS=true   # maintenance worker: jobs + webhook dispatch
```

**Best for:** a team-scale knowledge base or service desk on a single VM. Full guide:
[Local Deployment](local.md).

---

## 3. Container (Docker / Compose)

The repo ships a `Dockerfile` and `docker-compose.yml`: single-stage `python:3.12-slim`,
**non-root** (`uid 10001`), data in a `/data` volume, with a container `HEALTHCHECK`.

```bash
docker compose up --build
```

Data (SQLite + runtime exports) lives in the `archub-data` named volume and survives
`down`/`up`. **Best for:** reproducible single-replica installs. Full guide:
[Docker & Compose](docker.md).

---

## 4. PostgreSQL + multi-replica

For many concurrent ITSM agents or horizontal scaling, move the ITSM plugin (requests +
catalog/SLA/CMDB + persisted BPMN schemes) to **PostgreSQL** so replicas share state:

```bash
docker compose --profile itsm-postgres up --build
```

```yaml
services:
  archub:
    environment:
      ARCHUB_ITSM_PG_DSN: postgresql://archub:archub@postgres:5432/archub_itsm
```

Tables are created automatically on first use. Run several stateless app replicas behind
a load balancer; keep one writer for background jobs (`ARCHUB_BACKGROUND_JOBS=true`) to
avoid duplicate webhook dispatch.

!!! note "What stays on SQLite"
    Today, the **ITSM** context is the PostgreSQL-backed store; the rest of the CMS uses
    SQLite. For multi-replica CMS, place the SQLite database on shared storage or run the
    CMS write path on a single node. See the
    [hardening notes](docker.md#production-hardening).

**Best for:** scale-up ITSM, multiple replicas, shared state.

---

## 5. Air-gapped / offline

ArcHub's default mode is already air-gapped: **no network, no API keys, no Node**. Keep
`ARCHUB_LLM_PROVIDER=offline-extractive` (the default) and you get hybrid FTS5 search,
backlinks/graph and extractive answers entirely on local data.

```bash
# No outbound calls. SQLite + offline LLM.
python -m pip install -e ".[server]"      # from a local wheelhouse if fully offline
uvicorn archub_cms.app:create_archub_app --factory --host 0.0.0.0 --port 8088
```

Notes for sealed environments:

- Install from a **local wheel cache** (`pip install --no-index --find-links`).
- The docs site's PlantUML diagrams render via a public server by default — for offline
  docs, self-host PlantUML or pre-render the `.puml` sources (see `mkdocs.yml`).
- For *on-prem* generative answers, point the online provider at an internal
  OpenAI-compatible endpoint (vLLM / Ollama / TGI) — still no internet egress.

**Best for:** banks, defense, healthcare, government, OT/industrial.

---

## 6. Online LLM upgrade

Layer generative answers and online embeddings onto any scenario. A **circuit breaker**
degrades back to offline-extractive on failure, so availability never depends on the
provider.

```bash
export ARCHUB_LLM_PROVIDER=openai-compatible
export ARCHUB_LLM_BASE_URL=https://api.openai.com/v1   # or an on-prem endpoint
export ARCHUB_LLM_API_KEY=sk-...
export ARCHUB_LLM_MODEL=gpt-4o-mini
export ARCHUB_LLM_EMBEDDING_MODEL=text-embedding-3-small
export ARCHUB_LLM_TIMEOUT=15
```

**Best for:** richer "ask the docs" answers when policy permits an LLM endpoint.

---

## Cross-cutting concerns

### TLS & reverse proxy
The app speaks plain HTTP. Terminate TLS at nginx / Caddy / Traefik and forward to the
app port (8088 standalone, 8000 in the container).

### Persistence & backup
- **SQLite:** back up `ARCHUB_CMS_DB` (and `ARCHUB_RUNTIME_EXPORT_DIR`). Use SQLite online
  backup or snapshot the volume.
- **PostgreSQL:** standard `pg_dump` / managed backups for the ITSM database.

### Background worker
Set `ARCHUB_BACKGROUND_JOBS=true` to run scheduled jobs, webhook dispatch and
workflow/runtime upkeep. With multiple replicas, run it on **one** instance.

### Health & readiness
The container `HEALTHCHECK` probes `/api/docs`; wire it to your orchestrator's readiness
checks. The platform also exposes `/api/platform/report` for a runtime snapshot.

### Configuration
Everything is environment-driven — see the full
[Configuration reference](../reference/configuration.md). Nothing requires a config file.

---

## Decision guide

| If you… | Use |
|---|---|
| Already run a FastAPI app | [1. Embedded](#1-embedded-in-a-fastapi-app) |
| Want a single-VM install | [2. Standalone](#2-standalone-single-node) |
| Want reproducible containers | [3. Container](#3-container-docker-compose) |
| Have many ITSM agents / replicas | [4. PostgreSQL](#4-postgresql-multi-replica) |
| Cannot allow data egress | [5. Air-gapped](#5-air-gapped-offline) |
| Want generative answers | [6. Online LLM](#6-online-llm-upgrade) |
