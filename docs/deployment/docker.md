---
tags:
  - Deployment
  - Plugins
---

# Docker & Compose Deployment

The root `Dockerfile` builds the standalone FastAPI platform on `python:3.12-slim`.
It installs `.[server,postgres]`, runs as non-root `uid 10001`, persists `/data`, and
exposes a health check at `/api/docs`.

## Compose: SQLite Single Node

```bash
docker compose up --build
```

Open `http://127.0.0.1:8088/admin/archub`, `/admin/platform`, `/admin/itsm`,
`/cms`, and `/api/docs`.

Data is stored in the `archub-data` named volume:

```bash
docker compose down      # keep data
docker compose down -v   # remove data
```

## Compose: ITSM on PostgreSQL

```bash
docker compose --profile itsm-postgres up --build
```

Uncomment or set:

```yaml
services:
  archub:
    environment:
      ARCHUB_ITSM_PG_DSN: postgresql://archub:archub@postgres:5432/archub_itsm
```

Use this mode when several agents work ITSM tickets concurrently.

## Plain Docker

```bash
docker build -t archub-platform:local .

docker run --rm -p 8088:8000 \
  -e ARCHUB_BACKGROUND_JOBS=true \
  -e ARCHUB_PLUGIN_DIRS=/data/plugins \
  -v archub-data:/data \
  archub-platform:local
```

## Plugin Images

External PHP plugins run as separate containers:

```bash
docker build -t archub-ru-wiki-php plugins/archub_ru_wiki_php
docker run --rm -p 8097:8097 archub-ru-wiki-php

docker build -t archub-olo-php plugins/archub_olo_php
docker run --rm -p 8098:8098 archub-olo-php
```

Install their manifests through the marketplace, then enable them after health checks
pass. See [Plugin Release Distributions](../plugins/release-distributions.md).

## Build a Release Image

```bash
docker build -t registry.example.com/archub-platform:0.1.0 .
docker push registry.example.com/archub-platform:0.1.0
```

Use that tag in Kubernetes or Compose rather than `:local`.

## Environment

| Variable | Container default | Purpose |
|---|---|---|
| `ARCHUB_CMS_DB` | `/data/archub_cms.db` | SQLite database |
| `ARCHUB_RUNTIME_EXPORT_DIR` | `/data/archub_runtime` | runtime/RAG export |
| `ARCHUB_PLUGIN_DIRS` | `/app/plugins` | bundled plugin manifests |
| `ARCHUB_BACKGROUND_JOBS` | unset | scheduled jobs and webhook dispatch |
| `ARCHUB_ITSM_PG_DSN` | unset | optional PostgreSQL for ITSM |

## Production Notes

- Terminate TLS at nginx, Caddy, Traefik or an ingress controller.
- Run exactly one background worker when multiple replicas share state.
- Keep external plugins on their own services and enable manifests only after readiness.
- Store release marketplace archives outside the image and install them into
  `ARCHUB_PLUGIN_DIRS`.
- For clusters, continue with [Kubernetes Deployment](kubernetes.md).
