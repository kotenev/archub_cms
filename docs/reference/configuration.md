# Configuration

All configuration is environment-driven via `ArcHubSettings.from_env()` — no config
files required. Unset variables fall back to the defaults below.

## Core

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_CMS_DB` | `data/archub_cms.db` | SQLite database path (content, versions, FTS5, plugin config, ITSM data). Parent dirs are created automatically. |
| `ARCHUB_RUNTIME_EXPORT_DIR` | `data/archub_runtime` | Directory for runtime / RAG exports. |
| `ARCHUB_PUBLIC_ROOT` | `/cms` | Mount path for the public delivery surface. |
| `ARCHUB_PLUGIN_DIRS` | `plugins` | Comma-separated directories scanned for plugin manifests (`plugin.json`). |

## Delivery cache

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_DELIVERY_CACHE_MAX_AGE` | `60` | `max-age` (seconds) on public delivery responses. |
| `ARCHUB_DELIVERY_CACHE_STALE_REVALIDATE` | `300` | `stale-while-revalidate` (seconds). |

## Background worker

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_BACKGROUND_JOBS` | `false` | Enable the maintenance worker (scheduled jobs, webhook dispatch, workflow/runtime upkeep). Truthy values: `1/true/yes/on`. |
| `ARCHUB_BACKGROUND_JOB_INTERVAL` | `60` | Worker tick interval (seconds). |
| `ARCHUB_WEBHOOK_DISPATCH_LIMIT` | `50` | Max webhook deliveries per dispatch pass. |

## LLM & embeddings (knowledge base / RAG)

The default is a **fully offline** extractive provider — no network, no keys. Provide
an OpenAI-compatible endpoint to go online; a circuit breaker degrades back to offline
on failure.

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_LLM_PROVIDER` | `offline-extractive` | `offline-extractive` or `openai-compatible`. |
| `ARCHUB_LLM_BASE_URL` | _(empty)_ | OpenAI-compatible base URL (e.g. `https://api.openai.com/v1`). |
| `ARCHUB_LLM_API_KEY` | _(empty)_ | API key for the online provider. |
| `ARCHUB_LLM_MODEL` | _(empty)_ | Chat/completion model id. |
| `ARCHUB_LLM_EMBEDDING_MODEL` | _(empty)_ | Embedding model id (online semantic search). |
| `ARCHUB_LLM_TIMEOUT` | `15.0` | Online request timeout (seconds). |

## Media

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_ALLOWED_MEDIA_CONTENT_TYPES` | _(image/\*, video/mp4, audio/mpeg, pdf, text, json)_ | Comma-separated allow-list of upload content types. |

## ITSM plugin

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_ITSM_PG_DSN` | _(empty)_ | PostgreSQL DSN. When set (and the plugin `storage` is `postgres`), ITSM requests + reference data use PostgreSQL instead of SQLite. Also enables the PostgreSQL integration tests. |

ITSM plugin **settings** (per-plugin, via the plugin config store, not env) include
`project_prefix` (default `REQ`), `provider`, `storage` (`sqlite`/`postgres`) and
`dsn`. See [ITSM / ITIL](../capabilities/itsm.md#storage-backends).

## Programmatic overrides

`create_archub_app(seed_demo=False)` disables demo seeding. Settings can also be built
explicitly:

```python
from archub_cms.settings import ArcHubSettings

settings = ArcHubSettings.from_env({"ARCHUB_CMS_DB": "/tmp/test.db"})
```

## Optional dependency extras

| Extra | Installs | For |
|---|---|---|
| `server` | `uvicorn[standard]` | Running the ASGI app |
| `postgres` | `psycopg[binary]` | ITSM PostgreSQL backend |
| `docs` | ProperDocs, MkDocs Material, PlantUML, PyMdown, tags/search, glightbox, macros, redirects, minify, Git revision dates | Building this Docs-as-Code wiki |
| `test` | `httpx`, `pytest` | Running the test suite |
| `yaml` | `pyyaml` | YAML helpers |
| `release` | `build` | Building Python release artifacts |
