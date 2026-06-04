# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ArcHub CMS is a standalone, headless Python CMS (FastAPI + Pydantic + Jinja2, `src/` layout). See `AGENTS.md` for the longer-form contributor guide.

## Commands

Run from the repo root. `/checks` runs all of these in order.

- Install (with extras): `python -m pip install -e ".[server,yaml,test,docs]"`
- Lint (CI gate): `ruff check src tests`
- Format: `ruff format src tests`
- Syntax check (CI gate): `python -m compileall -q src`
- Tests: `pytest -q` — single test: `pytest tests/test_architecture_facades.py::test_name -q`
- Run demo app: `uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088`

Run `ruff check`, `ruff format`, `compileall`, and `pytest` locally before committing — CI runs all four on Python 3.11 and 3.12.

## Code style

Python 3.11+. Follow the Ruff config in `pyproject.toml`, which differs from defaults:
- Line length **100** (not 88); `E501` is disabled.
- **Double quotes**, space indentation, sorted imports.
- Type hints on public APIs.
- `snake_case` for modules/functions/fixtures/vars; `PascalCase` for classes (ports, services).

## Testing quirks

- Tests must call `get_archub_cms_service.cache_clear()` between cases — the service is cached and state leaks otherwise.
- Use `tmp_path` for isolated filesystem state; set `ARCHUB_CMS_DB` via `monkeypatch` when exercising persistence.

## Architecture boundary

Layered `domain/` → `application/` → `services/` → `web/`. Host-specific behavior must stay behind the `ports.py` abstractions (`AuthPort`, `TemplatePort`, `RuntimeSourcePort`, `CacheInvalidationPort`, `AuditSink`, `LLMProviderPort`) — never import host/app-specific packages directly. Note: `services/cms.py` (~350KB) and `web/routes.py` (~97KB) are large monoliths.

## Configuration & gotchas

- All config is environment-driven via `ARCHUB_*` vars (see `settings.py`), e.g. `ARCHUB_CMS_DB`, `ARCHUB_RUNTIME_EXPORT_DIR`, `ARCHUB_PLUGIN_DIRS`, `ARCHUB_LLM_*`.
- Never commit generated artifacts under `data/` (SQLite DBs, runtime exports), secrets, or host credentials.
- Commits: short imperative first line under ~72 chars; body only for rationale/migration notes.
