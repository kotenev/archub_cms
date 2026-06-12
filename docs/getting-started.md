# Getting Started

## Install

```bash
python -m pip install -e .[server]
```

## Run the standalone demo

```bash
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

The demo seeds a SQLite database at `data/archub_cms.db`.

Open:

- `http://127.0.0.1:8088/admin/archub` — CMS backoffice
- `http://127.0.0.1:8088/admin/itsm` — ITSM Service Desk
- `http://127.0.0.1:8088/admin/itsm/workflow` — visual BPMN workflow editor (offline)
- `http://127.0.0.1:8088/cms` — published site
- `http://127.0.0.1:8088/api/docs` — OpenAPI

!!! info "Deeper guides"
    - [Local deployment](deployment/local.md) (embedding, production) and
      [Docker & Compose](deployment/docker.md).
    - The full [Configuration](reference/configuration.md) reference and
      [HTTP API](reference/api.md) catalog.
    - [Capabilities overview](capabilities/index.md) and the
      [C4 architecture model](architecture/c4-model.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_CMS_DB` | `data/archub_cms.db` | SQLite CMS database |
| `ARCHUB_RUNTIME_EXPORT_DIR` | `data/archub_runtime` | Published runtime export directory |
| `ARCHUB_PUBLIC_ROOT` | `/cms` | Public delivery root |
| `ARCHUB_DELIVERY_CACHE_MAX_AGE` | `60` | Public max-age seconds |
| `ARCHUB_DELIVERY_CACHE_STALE_REVALIDATE` | `300` | Public stale-while-revalidate seconds |

## Embed in another FastAPI app

```python
from fastapi import FastAPI

from archub_cms.web.routes import router as archub_router

app = FastAPI()
app.include_router(archub_router)
```

For a full standalone app with static assets and seeded demo content:

```python
from archub_cms.app import create_archub_app

app = create_archub_app()
```
