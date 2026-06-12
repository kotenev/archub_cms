# Repository Guidelines

## Project Structure

ArcHub CMS is a standalone headless CMS and Content Builder for FastAPI hosts. Python `src/` layout; package is `archub_cms`.

Key directories under `src/archub_cms/`:
- `domain/` — bounded-context domain models (content, modeling, delivery, workflow, blueprints, etc.)
- `services/` — facade services: `cms.py` (legacy aggregate being decomposed), `content_builder.py`, `runtime.py`, `jobs.py`
- `infrastructure/db/` — `Database` connection factory shared everywhere; `infrastructure/sqlite/` — per-domain repositories
- `kernel/` — shared primitives: `result.py`, `specification.py`, `unit_of_work.py`, `circuit_breaker.py`, `events.py`
- `web/` — FastAPI route modules: `routes.py` (public delivery), `admin_routes.py`, `platform_routes.py`, `collaboration_routes.py`
- `extensibility/` — plugin host, event bus, config store, extension points
- `integrations/` — optional host integration hooks (e.g., RAG)
- `ports.py` — Protocol-based host contracts (`AuthPort`, `TemplatePort`, `RuntimeSourcePort`, `LLMProviderPort`, `EmbeddingPort`, `SearchPort`, `CacheInvalidationPort`, `AuditSink`)
- `settings.py` — environment-driven config via `ArcHubSettings.from_env()`

## Build, Test, and Development Commands

```bash
python -m pip install -e ".[server,yaml,test,docs]"   # install with all extras
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088  # standalone demo
pytest -q                                              # run tests
pytest tests/test_delivery.py -q                       # run a single test file
ruff check src tests                                   # lint
ruff format src tests                                  # format
python -m compileall -q src                            # syntax check
mkdocs build --site-dir site                           # build docs
```

CI gate runs in this order: **lint → syntax check → test** (see `.github/workflows/ci.yml`). CI tests on Python 3.11 and 3.12.

## Coding Style

Target Python 3.11+. Ruff settings in `pyproject.toml`: 100-char lines, double quotes, space indent, sorted imports, `py311` target. Ruff lint rules: `E, W, F, I, UP, B, C4, RET, SIM, PTH, RUF` (E501 and RUF001–003, RUF022 ignored). Use `snake_case` for modules/functions/variables, `PascalCase` for classes.

Host-specific behavior must stay behind `ports.py` Protocol abstractions — never import application-specific packages into `archub_cms`.

## Testing

Tests in `tests/` with `test_*.py` naming. Use `tmp_path` for isolated filesystem state and `monkeypatch` to set `ARCHUB_CMS_DB` when exercising persistence. The `data/` directory is gitignored — SQLite DBs and runtime exports are created at runtime.

## Configuration

All config is environment-driven. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `ARCHUB_CMS_DB` | `data/archub_cms.db` | SQLite database path |
| `ARCHUB_RUNTIME_EXPORT_DIR` | `data/archub_runtime` | Published runtime snapshot directory |
| `ARCHUB_PUBLIC_ROOT` | `/cms` | Public URL root |
| `ARCHUB_BACKGROUND_JOBS` | off | Set `1`/`true` to enable background worker |
| `ARCHUB_PLUGIN_DIRS` | `plugins` | Plugin search directories |
| `ARCHUB_LLM_PROVIDER` | `offline-extractive` | LLM provider mode |

Do not commit generated databases, runtime exports, secrets, or host credentials.

## Commit & PR Guidelines

Short, imperative summaries under ~72 characters. Body text only for rationale or migration notes. PRs: brief summary, testing performed, linked issues. Include screenshots/URLs for changes to `templates/`, `static/`, `docs/`, or `demo_site/`.

## Key Entry Points

- App factory: `src/archub_cms/app.py` → `create_archub_app()`
- Public import surface: `archub_cms.services.cms`, `archub_cms.services.content_builder`, `archub_cms.web.routes`
- Host embedding: `from archub_cms.web.routes import router as archub_router` then `app.include_router(archub_router)`
