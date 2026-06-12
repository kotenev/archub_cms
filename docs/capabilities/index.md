# Platform Capabilities

ArcHub is three products in one embeddable package, sharing a hexagonal/DDD core and a
real plugin runtime:

1. **Headless CMS & Content Builder** — document types, content tree, publishing.
2. **Enterprise Knowledge Base** — Confluence/Obsidian/Wiki.js-style features with
   offline **and** online LLM/RAG.
3. **ITSM/ITIL suite** — Service Desk, BPMN workflow engine, Service Catalog, SLA and
   CMDB.

This page is the capability index; deep-dives live in the linked pages.

## Capability catalog

| Area | Capability | Where |
|---|---|---|
| **Content** | Umbraco-style document types, reusable data types, templates | [Content Modeling](../architecture/content-modeling.md) |
| Content | Hierarchical tree: draft, publish, unpublish, trash/restore | [Publishing & Workflow](../architecture/publishing-workflow.md) |
| Content | Version history, preview/share tokens, redirects, domains, cultures, segments | [Versioning & Cleanup](../architecture/versioning-cleanup.md) |
| Content | Content Builder block registry with strict normalization + HTML rendering | [Content Builder](../content-builder.md) |
| **Delivery** | Published delivery API: content, tree, search, tags, RSS, sitemap | [Delivery API](../delivery-api.md) |
| Delivery | Cache headers (max-age + stale-while-revalidate), runtime/RAG exports | [Delivery Contracts](../architecture/delivery-contracts.md) |
| **Knowledge** | Hybrid lexical + semantic search, SQLite FTS5 (BM25, porter) | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Knowledge | Offline-extractive **and** online (OpenAI-compatible) LLM with circuit breaker | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Knowledge | Agentic tool-use answering, backlinks/graph, vault export | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| **ITSM** | Service Desk: incident/service request/problem/change requests, SLA, queue | [ITSM / ITIL](itsm.md) |
| ITSM | Jira-style **customizable workflow engine** (statuses, guarded transitions) | [ITSM / ITIL](itsm.md) |
| ITSM | **BPMN 2.0 engine** — lossless import/export + Mermaid; visual editor | [ITSM / ITIL](itsm.md) |
| ITSM | **10 best-practice ITIL workflow schemes** out of the box | [ITSM / ITIL](itsm.md) |
| ITSM | **Service Catalog**, **SLA management**, **CMDB** with impact analysis | [ITSM / ITIL](itsm.md) |
| ITSM | ITIL RBAC roles; SQLite **or** PostgreSQL storage | [ITSM / ITIL](itsm.md) |
| **Extensibility** | Plugin host: in-process (Python) + HTTP/sandboxed runtimes | [Plugins & Extensibility](plugins.md) |
| Extensibility | 25+ extension points (renderer, macro, search, LLM tool, editor, …) | [Plugins & Extensibility](plugins.md) |
| Extensibility | Audited platform persistence adapter (capability boundary for plugins) | [Plugin Platform Adapter](../architecture/plugin-platform-adapter.md) |
| Extensibility | Offline BPMN editor shipped **as a plugin** (no CDN) | [Plugins & Extensibility](plugins.md) |
| **Architecture** | Hexagonal ports/adapters, DDD bounded contexts, CQRS-lite | [C4 Model](../architecture/c4-model.md) |
| Architecture | Domain events + in-process bus, outbox, sagas, snapshots | [Bounded Contexts](../architecture/contexts.md) |
| **Ops** | Maintenance worker (scheduled jobs, webhook dispatch), audit trail | [Runtime & Data](../architecture/runtime-and-data.md) |
| Ops | Signed webhooks; Slack/Jira/GitHub connectors | [Webhook Integrations](../architecture/webhook-integrations.md) |

## Architectural patterns

The platform wires a catalog of patterns — surfaced at runtime via
`GET /api/platform/capabilities`:

Repository · Unit of Work · Domain Events + Event Bus · Hexagonal Ports/Adapters ·
CQRS-lite (command vs. query services) · Specification · Strategy (LLM/embedding/
storage providers) · Plugin/SPI · Result type · State Machine (workflow) · Outbox
(webhooks) · Circuit Breaker (online LLM resilience) · Saga / Process Manager ·
Aggregate Snapshots · Composition Root.

## Surfaces

| Surface | Path |
|---|---|
| CMS backoffice | `/admin/archub` |
| Platform dashboard | `/admin/platform` |
| ITSM Service Desk | `/admin/itsm` |
| Visual BPMN workflow editor | `/admin/itsm/workflow` |
| Published site | `/cms` |
| Platform API | `/api/platform/*` |
| ITSM API | `/api/platform/itsm/*` |
| OpenAPI / Swagger | `/api/docs` |

See the [HTTP API reference](../reference/api.md) for the endpoint catalog and
[Configuration](../reference/configuration.md) for every environment variable.
