# ArcHub CMS Extraction Plan

This document records the completed extraction work and the remaining host
integration steps for ArcHub CMS.

## Phase 0: product seam in the monorepo

Status: implemented.

- `products/archub_cms` is the future repository root.
- Apache-2.0 `LICENSE`, `NOTICE`, `README.md`, `pyproject.toml` and
  `MANIFEST.in` are present.
- Public imports exist under `archub_cms.*`.
- Product contracts exist in `archub_cms.ports` and `archub_cms.settings`.
- Wrappers were replaced by copied standalone implementation modules.

## Phase 1: move implementation modules

Status: implemented.

| Current path | Product path |
|---|---|
| `botplatform/web/services/archub_cms.py` | `src/archub_cms/services/cms.py` |
| `botplatform/web/services/archub_content_builder.py` | `src/archub_cms/services/content_builder.py` |
| `botplatform/web/services/archub_runtime.py` | `src/archub_cms/integrations/runtime.py` |
| `botplatform/web/routes/archub_cms.py` | `src/archub_cms/web/routes.py` |
| `botplatform/web/templates/archub_*.html` | `src/archub_cms/templates/` |
| `botplatform/web/static/js/archub_*.js` | `src/archub_cms/static/js/` |

The product also ships `base.html`, `style.css`, a standalone `_common.py`, a
demo app factory and demo content seeding.

## Phase 2: isolate host adapters

Status: partially implemented.

Replace direct host imports with ports and adapters:

- `AuthPort`: current user, admin check, permission subject;
- `TemplatePort`: Jinja environment and mounted static assets;
- `RuntimeSourcePort`: experts, RAG corpus specs and bot resource roots;
- `CacheInvalidationPort`: host process cache refresh hooks;
- `AuditSink`: structured event sink and counters.

The standalone release ships local defaults. The remaining work is to add
first-class dependency injection for custom host adapters instead of replacing
module-level functions.

## Phase 3: standalone app factory

Status: implemented.

Add an independent FastAPI app factory:

```python
from archub_cms.app import create_archub_app

app = create_archub_app()
```

The factory currently accepts `seed_demo`; the next release should accept
settings, storage backend, auth adapter and runtime integration adapters.

## Phase 4: repository publication

Status: ready.

Create the GitHub repository and copy this directory as the repository root.

Minimum repository files:

- `LICENSE`;
- `NOTICE`;
- `README.md`;
- `EXTRACTION.md`;
- `pyproject.toml`;
- `src/archub_cms/**`;
- `tests/**`;
- `.github/workflows/ci.yml`.
- `.github/workflows/pages.yml`.
- `docs/**`.
- `demo_site/**`.

Recommended CI:

```bash
python -m pip install -e .[server,yaml]
ruff check src tests
python -m py_compile $(find src -name '*.py')
pytest -q
```

## Phase 5: host migration

After the standalone package is installable:

1. Add `archub-cms` as a host dependency.
2. Replace `botplatform.web.services.archub_*` imports with `archub_cms.*`.
3. Keep only host-specific adapters and template shell integration in the bot
   web application.

## License boundary

ArcHub CMS is prepared as Apache-2.0. The product must not vendor AGPL or other
copyleft code. Optional integrations with AGPL services must remain network
calls or host-provided adapters outside the ArcHub source distribution.
