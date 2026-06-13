---
tags:
  - Deployment
  - CMS
  - ITSM
  - Plugins
---

# Getting Started

This path gets a local ArcHub platform running with the CMS, knowledge APIs, ITSM
service desk, plugin runtime and OpenAPI UI.

## 1. Install for Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[server,postgres,docs,test]"
```

For a release install, use the wheelhouse flow in
[Release Artifacts](deployment/release-artifacts.md).

## 2. Run the Platform

```bash
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

Open:

| URL | Surface |
|---|---|
| `http://127.0.0.1:8088/admin/archub` | CMS backoffice |
| `http://127.0.0.1:8088/admin/platform` | platform and plugin dashboard |
| `http://127.0.0.1:8088/admin/itsm` | ITSM Service Desk |
| `http://127.0.0.1:8088/admin/itsm/workflow` | offline BPMN workflow editor |
| `http://127.0.0.1:8088/cms` | published site |
| `http://127.0.0.1:8088/api/docs` | OpenAPI / Swagger UI |

Default state is written to `data/archub_cms.db` and `data/archub_runtime`.

## 3. Enable Release Plugins

Build a local marketplace and inspect it:

```bash
archub-marketplace-build --output dist/archub-marketplace --json
curl 'http://127.0.0.1:8088/api/platform/modules/marketplace?repository=dist/archub-marketplace'
```

Install a module:

```bash
curl -X POST http://127.0.0.1:8088/api/platform/modules/marketplace/install \
  -H 'Content-Type: application/json' \
  -d '{"repository":"dist/archub-marketplace","module_id":"archub.ru.wiki.php","enable":false}'
```

External plugins such as the PHP wiki and OLO demo must be running before you enable
their manifests. See [Plugin Release Distributions](plugins/release-distributions.md).

## 4. Choose a Deployment Mode

| Need | Use |
|---|---|
| source checkout / single VM | [Local Deployment](deployment/local.md) |
| release wheelhouse and module archives | [Release Artifacts](deployment/release-artifacts.md) |
| local container or Compose profile | [Docker & Compose](deployment/docker.md) |
| cluster with PVC/probes/Ingress | [Kubernetes](deployment/kubernetes.md) |
| documentation publishing | [GitHub Pages Docs](deployment/github-pages.md) |

## 5. Build the Documentation

```bash
properdocs serve --dev-addr 127.0.0.1:8001
properdocs build --strict --site-dir site
```

The canonical config is `properdocs.yml`; `mkdocs.yml` remains a compatibility shim.
The toolchain uses Material, search, tags, revision dates, lightbox, minification,
PlantUML and Mermaid. See [Documentation System](handbook/docs-as-code.md).
