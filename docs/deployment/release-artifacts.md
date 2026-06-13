---
tags:
  - Deployment
  - Plugins
  - SDK
---

# Release Artifacts

Use this guide when you install ArcHub from release outputs rather than from a
developer checkout. A release is normally composed of the Python platform package,
optional SDK package, plugin/module marketplace archives, and container images.

## Artifact Set

| Artifact | Producer | Consumer |
|---|---|---|
| `archub_cms-*.whl` / sdist | Python build pipeline | VM, container, offline wheelhouse |
| `archub-platform-sdk` | `sdk/python` package | automation, CI, marketplace clients |
| `dist/archub-marketplace/` | `archub-marketplace-build` | platform module installer |
| `archub-platform:<tag>` | Docker build/publish | Docker, Compose, Kubernetes |
| PHP plugin images | plugin Dockerfiles | external HTTP plugin runtime |

## Install Platform From a Wheelhouse

For online installs use your package index. For offline installs copy the wheelhouse
into the target environment and install with `--no-index`.

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --no-index --find-links ./wheelhouse \
  "archub-cms[server,postgres]==0.1.0"

export ARCHUB_CMS_DB=/var/lib/archub/archub_cms.db
export ARCHUB_RUNTIME_EXPORT_DIR=/var/lib/archub/runtime
export ARCHUB_PLUGIN_DIRS=/var/lib/archub/plugins
export ARCHUB_BACKGROUND_JOBS=true

uvicorn archub_cms.app:create_archub_app --factory --host 0.0.0.0 --port 8088
```

Use `postgres` only when the ITSM plugin needs PostgreSQL. The default platform runs
with SQLite and the offline-extractive LLM.

## Build Release Artifacts From This Repository

```bash
python -m pip install -e ".[server,postgres,docs,test,release]"
python -m build
archub-sdk-release --json > dist/archub-sdk-release.json
archub-marketplace-build --output dist/archub-marketplace --json
docker build -t archub-platform:0.1.0 .
```

The marketplace command writes a hierarchical repository:

```text
dist/archub-marketplace/
  marketplace.json
  cms/archub.cms.core/0.1.0/archub.cms.core-0.1.0.zip
  knowledge/archub.knowledge.spaces/0.1.0/...
  workflow/archub.itsm.service_desk/1.0.0/...
```

Each item includes `sha256`, `runtime`, `capability`, `permissions`, `core`,
`language`, `rust_crate`, and `provides`.

## Install Modules From a Release

Install from a local file:

```bash
curl -X POST http://127.0.0.1:8088/api/platform/modules/install/file \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "/srv/releases/archub.cms.core-0.1.0.zip",
    "replace": true,
    "enable": true
  }'
```

Install from a marketplace repository:

```bash
curl -X POST http://127.0.0.1:8088/api/platform/modules/marketplace/install \
  -H 'Content-Type: application/json' \
  -d '{
    "repository": "/srv/releases/archub-marketplace",
    "module_id": "archub.ru.wiki.php",
    "enable": false
  }'
```

Keep external HTTP plugins disabled until their service is reachable. Then enable
them from `/admin/platform` or `POST /api/platform/plugins/{plugin_id}/enable`.

## SDK Release

```bash
python -m pip install ./sdk/python
python -m archub_cms.tools.sdk_release --json
```

The SDK covers platform capabilities, core plugins, module marketplace workflows,
delivery API, knowledge search/answers, and runtime export.

## Offline Promotion Checklist

- Build wheels, SDK, marketplace and images in CI.
- Copy artifacts into the controlled environment.
- Verify checksums from `marketplace.json`.
- Install platform package from the local wheelhouse.
- Set `ARCHUB_PLUGIN_DIRS` to a writable plugin/module directory.
- Install only approved module archives.
- Run `properdocs build --strict --site-dir site` from the same release tag.
