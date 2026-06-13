---
tags:
  - Deployment
  - Plugins
---

# Local Deployment

Local deployment is the fastest way to run ArcHub without Docker. It uses SQLite and
the offline-extractive LLM by default; PostgreSQL and online LLMs are optional.

## Requirements

- Python 3.11+.
- `pip` and `venv`.
- Optional: PostgreSQL for ITSM concurrency.
- Optional: Composer/PHP 8.4 for external PHP plugin demos.

## Source Checkout

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[server,postgres,docs,test]"
```

Run:

```bash
export ARCHUB_CMS_DB=data/archub_cms.db
export ARCHUB_RUNTIME_EXPORT_DIR=data/archub_runtime
export ARCHUB_PLUGIN_DIRS=plugins
export ARCHUB_BACKGROUND_JOBS=true

uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

## Release Wheelhouse

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --no-index --find-links ./wheelhouse \
  "archub-cms[server,postgres]==0.1.0"

export ARCHUB_PLUGIN_DIRS=/var/lib/archub/plugins
uvicorn archub_cms.app:create_archub_app --factory --host 0.0.0.0 --port 8088
```

For release modules, use [Release Artifacts](release-artifacts.md).

## Useful URLs

| URL | Purpose |
|---|---|
| `/admin/archub` | CMS backoffice |
| `/admin/platform` | platform, core plugins and marketplace controls |
| `/admin/itsm` | ITIL Service Desk |
| `/admin/itsm/workflow` | offline BPMN editor |
| `/cms` | published delivery site |
| `/api/docs` | OpenAPI |
| `/api/platform/report` | runtime platform report |

## Optional PostgreSQL for ITSM

```bash
export ARCHUB_ITSM_PG_DSN=postgresql://archub:archub@localhost:5432/archub_itsm
```

The ITSM plugin will create request, catalog, SLA, CMDB and workflow tables on first
use. CMS content still uses the configured `ARCHUB_CMS_DB`.

## Optional Online LLM

```bash
export ARCHUB_LLM_PROVIDER=openai-compatible
export ARCHUB_LLM_BASE_URL=https://llm.internal/v1
export ARCHUB_LLM_API_KEY=...
export ARCHUB_LLM_MODEL=gpt-4o-mini
```

If the provider fails, the circuit breaker falls back to offline-extractive answers.

## Run External PHP Plugins

```bash
cd plugins/archub_ru_wiki_php
composer install
composer serve

cd ../archub_olo_php
composer install
composer serve
```

The wiki listens on `8097`, OLO on `8098`. Enable their manifests only after
`/health` responds.

## Embed in Another FastAPI App

```python
from fastapi import FastAPI
from archub_cms.web.routes import router as archub_router
from archub_cms.web.platform_routes import platform_router

app = FastAPI()
app.include_router(archub_router)
app.include_router(platform_router)
```

For the full standalone app:

```python
from archub_cms.app import create_archub_app

app = create_archub_app(seed_demo=False)
```

## Local Verification

```bash
ruff check src tests
python -m compileall -q src
pytest -q
properdocs build --strict --site-dir site
```
