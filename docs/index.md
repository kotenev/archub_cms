# ArcHub Platform

ArcHub is a standalone, embeddable **knowledge & ITSM platform** for FastAPI hosts —
shipped as one Apache-2.0 Python package (`archub_cms`). It combines a headless CMS, an
enterprise knowledge base with offline **and** online RAG, and a full **ITSM/ITIL**
suite, on a hexagonal/DDD core with a real plugin runtime.

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting Started](getting-started.md)** — install and run in
  one command.
- :material-server: **[Deployment](deployment/local.md)** — local (no Docker) and
  [Docker/Compose](deployment/docker.md).
- :material-shape: **[Capabilities](capabilities/index.md)** — the full feature catalog.
- :material-sitemap: **[C4 Architecture](architecture/c4-model.md)** — PlantUML C4
  context/container/component.
- :material-ticket-confirmation: **[ITSM / ITIL](capabilities/itsm.md)** — Service Desk,
  BPMN engine, Catalog, SLA, CMDB.
- :material-puzzle: **[Plugins](capabilities/plugins.md)** — the extensibility runtime.

</div>

## What's inside

### Headless CMS & Content Builder
Umbraco-style document types, reusable data types and templates; a hierarchical content
tree with draft / publish / unpublish / trash; version history, preview tokens,
redirects, domains, cultures and segments; a Content Builder block registry with strict
normalization and HTML rendering; and a published **delivery API** (content, tree,
search, tags, RSS, sitemap) with cache headers and runtime/RAG exports.

### Enterprise Knowledge Base (offline + online LLM)
Hybrid lexical + semantic search over SQLite **FTS5** (BM25, porter stemming); a fully
**offline-extractive** LLM by default and an **OpenAI-compatible** online provider with
a **circuit breaker** that degrades gracefully; agentic tool-use answering, backlinks /
graph, and Obsidian vault export.

### ITSM / ITIL suite
A cloud Service Desk with a **Jira-style customizable workflow engine**, a real **BPMN
2.0 engine** (lossless import/export + Mermaid, plus an **offline visual editor**),
**10 best-practice ITIL workflow schemes**, and the core practices — **Service
Catalog**, **SLA management** and a **CMDB** with impact analysis — over SQLite or
PostgreSQL. See [ITSM / ITIL](capabilities/itsm.md).

### Extensibility
A plugin **host** with in-process (Python) and HTTP/sandboxed runtimes, 25+ extension
points, manifest permissions, and an **audited platform persistence adapter**. UI
capabilities ship as plugins too — including the **offline BPMN editor**.

## Quick links

| Surface | Path |
|---|---|
| CMS backoffice | `/admin/archub` |
| Platform dashboard | `/admin/platform` |
| ITSM Service Desk | `/admin/itsm` |
| Visual BPMN editor | `/admin/itsm/workflow` |
| Published site | `/cms` |
| OpenAPI / Swagger | `/api/docs` |

## License

ArcHub is released under Apache-2.0.
