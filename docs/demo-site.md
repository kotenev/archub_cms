---
tags:
  - Deployment
---

# Static Demo Site

The repository includes a static GitHub Pages demo under `demo_site/`.

It is intentionally static: GitHub Pages cannot run the FastAPI backoffice, so
the static demo explains the product and links to the local live demo commands.

The live demo is the FastAPI app:

```bash
python -m pip install -e .[server]
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

The GitHub Pages workflow copies `demo_site/` into `site/demo/` after
`properdocs build --strict --site-dir site`, then uploads one Pages artifact.

For the live platform use [Getting Started](getting-started.md), [Docker](deployment/docker.md)
or [Kubernetes](deployment/kubernetes.md).
