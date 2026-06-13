---
tags:
  - Deployment
  - Kubernetes
---

# Kubernetes Deployment

Kubernetes deployment is a containerized ArcHub install with persistent `/data`,
environment-driven configuration, and HTTP probes. Start with one replica when using
SQLite. Use PostgreSQL-backed contexts and a single background worker before scaling
out.

## Build and Publish the Image

```bash
docker build -t registry.example.com/archub-platform:0.1.0 .
docker push registry.example.com/archub-platform:0.1.0
```

The root `Dockerfile` runs as non-root `uid 10001`, stores state in `/data`, exposes
`:8000`, and includes the same dependencies as `.[server,postgres]`.

## Apply the Baseline Manifest

```bash
kubectl apply -f deploy/kubernetes/archub-platform.yaml
kubectl -n archub rollout status deploy/archub-platform
kubectl -n archub port-forward svc/archub-platform 8088:80
```

Open:

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8088/admin/archub` | CMS backoffice |
| `http://127.0.0.1:8088/admin/platform` | platform/plugin dashboard |
| `http://127.0.0.1:8088/admin/itsm` | ITSM web interface |
| `http://127.0.0.1:8088/api/docs` | OpenAPI |

## Configuration Model

The manifest uses a `ConfigMap` for safe defaults:

```yaml
ARCHUB_CMS_DB: /data/archub_cms.db
ARCHUB_RUNTIME_EXPORT_DIR: /data/archub_runtime
ARCHUB_PLUGIN_DIRS: /data/plugins
ARCHUB_BACKGROUND_JOBS: "true"
ARCHUB_LLM_PROVIDER: offline-extractive
```

Put secrets in Kubernetes `Secret` objects, never in Git:

```bash
kubectl -n archub create secret generic archub-llm \
  --from-literal=ARCHUB_LLM_API_KEY='...' \
  --from-literal=ARCHUB_LLM_BASE_URL='https://llm.internal/v1' \
  --from-literal=ARCHUB_LLM_MODEL='gpt-4o-mini'
```

Then reference it with `envFrom.secretRef` in the `Deployment`.

## Scaling Rules

| Mode | Replica guidance |
|---|---|
| SQLite-only CMS | one writer replica; backup PVC snapshots |
| ITSM PostgreSQL | app replicas can share ITSM state via `ARCHUB_ITSM_PG_DSN` |
| Background jobs | run `ARCHUB_BACKGROUND_JOBS=true` on exactly one deployment |
| External plugins | deploy plugin services separately and enable their manifests after readiness |

For multi-replica platform installs, prefer a managed PostgreSQL endpoint for ITSM and
any plugin data that requires concurrency. Keep SQLite on a single writer or shared
storage with explicit operational controls.

## Marketplace Modules on Kubernetes

Mount a marketplace repository or copy module ZIPs into an init workflow, then install
through the platform API:

```bash
kubectl -n archub cp dist/archub-marketplace \
  deploy/archub-platform-0:/data/releases/archub-marketplace

kubectl -n archub exec deploy/archub-platform -- \
  python -m archub_cms.tools.sdk_release --json
```

For production, make module promotion a CI/CD step: verify `sha256`, install into
`/data/plugins`, and restart the deployment so manifests are rediscovered.

## Ingress

Terminate TLS at an ingress controller or a service mesh. Forward to
`svc/archub-platform:80`, preserve `X-Forwarded-*` headers, and restrict `/admin/*`
with your perimeter authentication until platform auth ports are wired to the host.

## Operational Checks

```bash
kubectl -n archub get pods,svc,pvc
kubectl -n archub logs deploy/archub-platform
kubectl -n archub exec deploy/archub-platform -- python -m compileall -q /usr/local/lib/python*
```

The liveness/readiness probes hit `/api/docs`. For a richer runtime check, query
`/api/platform/report`.
