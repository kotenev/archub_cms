---
tags:
  - Deployment
  - SDK
---

# Release Notes

## Documentation Wiki Refresh

- Reorganized MkDocs into a task-first Docs-as-Code wiki.
- Added release artifact, marketplace, Docker, Kubernetes and plugin deployment guides.
- Enabled search, tags, lightbox, revision dates, redirects, macros and minify
  plugins in the docs profile.
- Added a Kubernetes baseline manifest under `deploy/kubernetes/`.

## SDK 1.0.0

- Added `archub-platform-sdk`, a dependency-free Python SDK for platform,
  plugin, marketplace, delivery, knowledge and runtime APIs.
- Added SDK release manifest: `sdk/release/archub-sdk-1.0.0.json`.
- Added SDK OpenAPI subset: `sdk/openapi/archub-platform-sdk.openapi.yaml`.
- Added `archub-sdk-release` CLI for release metadata.
- Documented API groups, technology stack and SDK capabilities in MkDocs.

## 0.1.0

ArcHub CMS 0.1.0 is the first standalone release.

- Extracted CMS, Content Builder, runtime export and web routes into
  `src/archub_cms`.
- Added package-owned templates, static assets and standalone `base.html`.
- Added FastAPI app factory and seeded demo content.
- Added product ports, settings and standalone RAG registry.
- Added GitHub Actions CI and Pages workflows.
- Added MkDocs documentation and static GitHub Pages demo.
