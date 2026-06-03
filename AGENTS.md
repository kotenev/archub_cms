# Repository Guidelines

## Project Structure & Module Organization

ArcHub CMS is a Python package using a `src/` layout. Core package code lives in `src/archub_cms/`: `services/` contains CMS, content builder, and runtime export logic; `web/` contains FastAPI routes; `integrations/` contains optional host integration hooks; `templates/` and `static/` hold shipped UI assets. Tests live in `tests/`. MkDocs content is in `docs/`, and the static GitHub Pages demo is in `demo_site/`.

## Build, Test, and Development Commands

- `python -m pip install -e ".[server,yaml,test,docs]"`: install the package locally with server, YAML, test, and docs extras.
- `uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088`: run the standalone demo app.
- `ruff check src tests`: run lint checks used by CI.
- `ruff format src tests`: format Python files with the configured Ruff formatter.
- `python -m compileall -q src`: perform the CI syntax check.
- `pytest -q`: run the test suite.
- `mkdocs build --site-dir site`: build documentation locally.

## Coding Style & Naming Conventions

Target Python 3.11+. Use type hints for public APIs and keep modules under the `archub_cms` product boundary. Follow Ruff settings in `pyproject.toml`: 100-character line length, double quotes, space indentation, sorted imports, and Python 3.11 upgrade rules. Use `snake_case` for modules, functions, fixtures, and variables; `PascalCase` for classes such as ports and services. Keep host-specific behavior behind `ports.py` abstractions instead of importing application-specific packages.

## Testing Guidelines

Tests use `pytest` and are discovered from `tests/` with `test_*.py` naming. Prefer isolated filesystem state with `tmp_path` and set `ARCHUB_CMS_DB` through `monkeypatch` when exercising persistence. Add coverage for route registration, public delivery behavior, content seeding, and product-boundary regressions when those areas change. CI runs tests on Python 3.11 and 3.12.

## Commit & Pull Request Guidelines

Recent history uses short, imperative summaries such as `Prepare ArcHub CMS standalone release`. Keep the first line focused and under about 72 characters; add body text only for rationale or migration notes. Pull requests should include a brief summary, testing performed, linked issues when applicable, and screenshots or URLs for changes touching `templates/`, `static/`, `docs/`, or `demo_site/`.

## Security & Configuration Tips

Configuration is environment-driven. Local defaults create SQLite/runtime files under `data/`; do not commit generated databases, runtime exports, secrets, or host credentials. Use `ARCHUB_CMS_DB`, `ARCHUB_RUNTIME_EXPORT_DIR`, and delivery cache variables to isolate local and test runs.
