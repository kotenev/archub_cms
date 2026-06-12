# Local Deployment (without Docker)

ArcHub is a single Python package with **zero required services** — it runs on an
embedded SQLite database and an offline LLM by default, so a laptop with Python is
enough. PostgreSQL and an online LLM are optional upgrades.

## Requirements

- Python **3.11+** (CI targets 3.11; the repo is developed on 3.14).
- `pip` / `venv`. No Node, no database server required for the default setup.

## 1. Create a virtualenv and install

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip

# Editable install with the ASGI server extra:
python -m pip install -e ".[server]"

# Optional extras:
#   .[postgres]  PostgreSQL backend for the ITSM plugin (psycopg)
#   .[docs]      build the documentation site (mkdocs + PlantUML)
#   .[test]      run the test suite (pytest + httpx)
python -m pip install -e ".[server,postgres]"
```

## 2. Run the standalone app

```bash
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

`create_archub_app()` boots the plugin runtime, seeds demo content into a SQLite
database (`data/archub_cms.db` by default), and mounts every router.

Open:

| URL | What |
|---|---|
| `http://127.0.0.1:8088/admin/archub` | CMS backoffice |
| `http://127.0.0.1:8088/admin/platform` | Platform dashboard |
| `http://127.0.0.1:8088/admin/itsm` | ITSM Service Desk dashboard |
| `http://127.0.0.1:8088/admin/itsm/workflow` | Visual BPMN workflow editor (offline) |
| `http://127.0.0.1:8088/cms` | Published site |
| `http://127.0.0.1:8088/api/docs` | OpenAPI / Swagger UI |
| `http://127.0.0.1:8088/api/platform/itsm/schemes` | ITIL workflow scheme library (JSON) |

!!! tip "Run it without installing"
    From a checkout you can use the `!` prefix in tooling shells, or simply run the
    module directly after `pip install -e .[server]`. The factory string
    `archub_cms.app:create_archub_app` is all uvicorn needs.

## 3. Configure (optional)

All configuration is environment-driven (see the full table in
[Configuration](../reference/configuration.md)). A few common ones:

```bash
# Persist data outside the repo:
export ARCHUB_CMS_DB=/var/lib/archub/archub_cms.db
export ARCHUB_RUNTIME_EXPORT_DIR=/var/lib/archub/runtime

# Enable the maintenance worker (scheduled jobs, webhook dispatch):
export ARCHUB_BACKGROUND_JOBS=true

# Online LLM (OpenAI-compatible). Omit for the offline-extractive default:
export ARCHUB_LLM_PROVIDER=openai-compatible
export ARCHUB_LLM_BASE_URL=https://api.openai.com/v1
export ARCHUB_LLM_API_KEY=sk-...
export ARCHUB_LLM_MODEL=gpt-4o-mini

# Route the ITSM plugin to PostgreSQL instead of SQLite:
export ARCHUB_ITSM_PG_DSN=postgresql://archub:archub@localhost:5432/archub_itsm
```

## 4. Embed in an existing FastAPI app

ArcHub is designed to be embedded. Mount only what you need:

```python
from fastapi import FastAPI
from archub_cms.web.routes import router as archub_router
from archub_cms.web.platform_routes import platform_router
from archub_cms.web.itsm_routes import itsm_router, itsm_web_router

app = FastAPI()
app.include_router(archub_router)       # public + backoffice
app.include_router(platform_router)     # /api/platform/*
app.include_router(itsm_router)         # /api/platform/itsm/*
app.include_router(itsm_web_router)     # /admin/itsm + workflow editor
```

…or take the whole batteries-included app:

```python
from archub_cms.app import create_archub_app
app = create_archub_app(seed_demo=False)   # skip demo seeding in production
```

## 5. Run the tests

```bash
python -m pip install -e ".[server,test]"
ruff check src tests
python -m pytest -q
```

The PostgreSQL integration tests are skipped unless `ARCHUB_ITSM_PG_DSN` is set and
`psycopg` is installed.

## 6. Production notes

- Put a process manager (systemd, supervisor) in front of uvicorn, or run
  `gunicorn -k uvicorn.workers.UvicornWorker 'archub_cms.app:create_archub_app'`.
- Use `seed_demo=False` and point `ARCHUB_CMS_DB` at a persistent path (or Postgres
  for ITSM via `ARCHUB_ITSM_PG_DSN`).
- Terminate TLS at a reverse proxy (nginx/Caddy/Traefik).
- See [Docker & Compose](docker.md) for a containerized equivalent.
