# ArcHub CMS

ArcHub CMS is a standalone headless CMS and Content Builder for FastAPI hosts.
It originated as the bot web backoffice CMS and is now prepared as an
independent GitHub repository under the Apache-2.0 license.

## Local installation from the monorepo

```bash
pip install -e products/archub_cms
```

After the package is installed, host code can import `archub_cms.*` directly.

## Run the live demo

```bash
python -m pip install -e .[server]
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

Open:

- Backoffice: `http://127.0.0.1:8088/admin/archub`
- Published site: `http://127.0.0.1:8088/cms`
- API docs: `http://127.0.0.1:8088/api/docs`

## Product scope

ArcHub CMS owns:

- structured content models, document types, data types, templates and variants;
- hierarchical content nodes with draft, review, published and trashed states;
- content permissions, public access rules, workflow, scheduling and locks;
- headless delivery, preview tokens, route redirects, domains and cultures;
- Content Builder blocks, blueprints, sanitization and public rendering;
- editable runtime content for bot resources and AI-expert RAG corpora.

ArcHub CMS does not own domain-specific astrology, Telegram bot logic, RAG
generation models or astronomical calculations. Those remain host-product
integrations that consume published ArcHub content.

## Public imports

Use the product imports in new code:

```python
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.services.content_builder import get_archub_content_builder_service
from archub_cms.web.routes import router as archub_router
```

The implementation lives inside this package; there are no runtime imports from
the original host application.

## Product architecture

The package already defines the target standalone contracts:

- `archub_cms.settings.ArcHubSettings` for environment-backed configuration;
- `archub_cms.ports.AuthPort` for host authentication and editor identity;
- `archub_cms.ports.TemplatePort` for rendering integration;
- `archub_cms.ports.RuntimeSourcePort` for host-specific expert, RAG and
  resource imports;
- `archub_cms.ports.CacheInvalidationPort` and `AuditSink` for side effects.

The standalone web defaults are intentionally simple. Production hosts should
wire these ports to their own authentication, audit and runtime-source systems.

## Embedding in a FastAPI host

```python
from fastapi import FastAPI

from archub_cms.web.routes import router as archub_router

app = FastAPI()
app.include_router(archub_router)
```

The standalone package ships its own templates, static assets and demo content.

## Configuration

The standalone implementation reads these environment variables:

| Variable | Purpose |
|---|---|
| `ARCHUB_CMS_DB` | SQLite database path, default `data/archub_cms.db` |
| `ARCHUB_RUNTIME_EXPORT_DIR` | published runtime snapshot directory, default `data/archub_runtime` |

## GitHub repository preparation

This directory is intentionally self-contained:

- Apache-2.0 license and notice files are present;
- package metadata is declared in `pyproject.toml`;
- `MANIFEST.in` includes source and product docs;
- product sources live under `src/archub_cms`;
- `EXTRACTION.md` documents the completed migration and remaining host work.

Recommended repository name: `archub-cms/archub_cms`.

## Documentation and demo site

- MkDocs sources live in `docs/`.
- Static GitHub Pages demo lives in `demo_site/`.
- `.github/workflows/pages.yml` builds docs and publishes the static demo under
  `/demo/`.

## License

ArcHub CMS is prepared under the Apache License, Version 2.0. This permissive
license is compatible with commercial and open-source embedding and keeps the CMS
separate from optional copyleft services in the wider astrology platform.
