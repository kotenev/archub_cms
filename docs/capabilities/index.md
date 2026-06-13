# Capability Catalog

ArcHub is three products in one embeddable package, sharing a hexagonal/DDD core and a
real plugin runtime:

1. **Headless CMS & Content Builder** — document types, content tree, publishing.
2. **Enterprise Knowledge Base** — Confluence/Obsidian/Wiki.js-style features with
   offline **and** online LLM/RAG.
3. **ITSM/ITIL suite** — Service Desk, BPMN workflow engine, Service Catalog, SLA, CMDB.

This page is the **complete, categorized feature list**. Each row links to the deep-dive
that documents it. The platform also describes itself at runtime via
`GET /api/platform/capabilities`.

---

## 1. Content management (Headless CMS)

| Capability | Notes | Where |
|---|---|---|
| Document types (content types) | Umbraco-style, composable definitions | [Content Modeling](../architecture/content-modeling.md) |
| Reusable data types | Typed, configurable property editors | [Content Modeling](../architecture/content-modeling.md) |
| Templates | Bind document types to rendering templates | [Content Modeling](../architecture/content-modeling.md) |
| Compositions & blueprints | Mixins and pre-filled starting content | [Content Modeling](../architecture/content-modeling.md) |
| Hierarchical content tree | Parent/child nodes, ordering, move, duplicate | [Publishing & Workflow](../architecture/publishing-workflow.md) |
| Draft / publish / unpublish | Explicit publication lifecycle | [Publishing & Workflow](../architecture/publishing-workflow.md) |
| Trash / restore / purge | Recycle bin with restore and hard purge | [Versioning & Cleanup](../architecture/versioning-cleanup.md) |
| Version history & restore | Per-node versions, restore, scheduled cleanup | [Versioning & Cleanup](../architecture/versioning-cleanup.md) |
| Edit locks | Co-author safety, lock ownership | [Publishing & Workflow](../architecture/publishing-workflow.md) |
| Preview / share tokens | Time-boxed preview of unpublished content | [Versioning & Cleanup](../architecture/versioning-cleanup.md) |
| Redirects | Managed URL redirects | [Publishing & Workflow](../architecture/publishing-workflow.md) |
| Domains & cultures | Multi-domain, multi-culture (i18n) routing | [Content Modeling](../architecture/content-modeling.md) |
| Variants & segments | Per-culture variants and audience segments | [Versioning & Cleanup](../architecture/versioning-cleanup.md) |
| Content Builder blocks | Block registry, strict normalization, HTML render | [Content Builder](../content-builder.md) |
| Content health & analytics | Health report, analytics dashboard | [Runtime & Data](../architecture/runtime-and-data.md) |

## 2. Content delivery (headless API)

| Capability | Notes | Where |
|---|---|---|
| Published content API | Fetch published nodes as JSON | [Delivery API](../delivery-api.md) |
| Tree / navigation API | Published tree for menus & nav | [Delivery API](../delivery-api.md) |
| Delivery search | Search across published content | [Delivery API](../delivery-api.md) |
| Tags & taxonomy | Tag listing and filtering | [Delivery API](../delivery-api.md) |
| RSS & sitemap | Auto-generated feeds and `sitemap.xml` | [Delivery API](../delivery-api.md) |
| HTTP cache headers | `max-age` + `stale-while-revalidate` | [Delivery Contracts](../architecture/delivery-contracts.md) |
| Runtime / RAG export | Snapshot published content for runtimes & RAG | [Runtime & Data](../architecture/runtime-and-data.md) |
| Configurable public root | Mount delivery anywhere (`ARCHUB_PUBLIC_ROOT`) | [Configuration](../reference/configuration.md) |

## 3. Knowledge base & RAG (offline + online)

| Capability | Notes | Where |
|---|---|---|
| Lexical search (FTS5) | SQLite FTS5, BM25 ranking, porter stemming | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Semantic search | Vector embeddings (offline hashing or online model) | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Hybrid ranking | Lexical + semantic fused scoring | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Offline-extractive LLM | Default; no network, no API keys | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Online OpenAI-compatible LLM | Any compatible endpoint via env vars | [Configuration](../reference/configuration.md) |
| Circuit breaker | Auto-degrade online → offline on failure | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Agentic tool-use answering | Tool-using RAG answer endpoint | [HTTP API](../reference/api.md) |
| Backlinks & knowledge graph | Obsidian-style graph read model | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |
| Vault export | Export to an Obsidian-compatible vault | [Enterprise Knowledge Platform](../architecture/enterprise-knowledge-platform.md) |

## 4. ITSM / ITIL suite

| Capability | Notes | Where |
|---|---|---|
| Service Desk | Incidents, service requests, problems, changes | [ITSM / ITIL](itsm.md) |
| Request queue & SLA breaches | Queue counts, response/resolution breach view | [ITSM / ITIL](itsm.md) |
| Customizable workflow engine | Jira-style statuses + guarded transitions | [ITSM / ITIL](itsm.md) |
| BPMN 2.0 engine | Lossless import/export, Mermaid rendering | [ITSM / ITIL](itsm.md) |
| Offline visual BPMN editor | Ships as a plugin, no CDN required | [Plugins & Extensibility](plugins.md) |
| 10 ITIL workflow schemes | Best-practice schemes out of the box | [ITSM / ITIL](itsm.md) |
| Service Catalog | Offerings with ownership & metadata | [ITSM / ITIL](itsm.md) |
| SLA management | SLA policies, targets, breach detection | [ITSM / ITIL](itsm.md) |
| CMDB & impact analysis | Configuration items, relationships, blast radius | [ITSM / ITIL](itsm.md) |
| ITIL RBAC | Practice-aligned roles & permissions | [ITSM / ITIL](itsm.md) |
| SQLite **or** PostgreSQL | Per-deployment storage backend | [ITSM / ITIL](itsm.md#storage-backends) |

## 5. Extensibility & plugins

| Capability | Notes | Where |
|---|---|---|
| Plugin host | Loads enabled plugins at boot | [Plugins & Extensibility](plugins.md) |
| In-process Python runtime | `importlib` entrypoints, in-VM speed | [Plugins & Extensibility](plugins.md) |
| HTTP / external runtime | Sandboxed tools; PHP modules supported | [Plugin Platform Adapter](../architecture/plugin-platform-adapter.md) |
| 25+ extension points | Renderer, macro, search, LLM tool, editor, storage, auth, notification, workflow… | [Plugins & Extensibility](plugins.md) |
| Manifest permissions | Declared capabilities gated at the call boundary | [Plugins & Extensibility](plugins.md) |
| Per-plugin config store | Enable/disable/settings persistence | [Plugins & Extensibility](plugins.md) |
| Audited platform adapter | Capability boundary for plugin persistence | [Plugin Platform Adapter](../architecture/plugin-platform-adapter.md) |
| Module marketplace packager | Signed bundles with hashes & contracts | [Module Marketplace](../architecture/module-marketplace.md) |
| PHP plugins | [Wiki](../plugins/archub-ru-wiki-php.md) & [OurLifeOrganized](../plugins/archub-olo-php.md) | external runtime |
| Self-describing capabilities | `GET /api/platform/capabilities` | [HTTP API](../reference/api.md) |

## 6. Integrations & operations

| Capability | Notes | Where |
|---|---|---|
| Maintenance worker | Scheduled jobs, webhook dispatch, upkeep | [Runtime & Data](../architecture/runtime-and-data.md) |
| Signed webhooks (outbox) | Reliable, retried delivery via outbox | [Webhook Integrations](../architecture/webhook-integrations.md) |
| Slack / Jira / GitHub connectors | Outbound integration targets | [Webhook Integrations](../architecture/webhook-integrations.md) |
| Audit trail | `AuditSink` port for governance | [Governance & Access](../architecture/governance-access.md) |
| Platform report & route index | `/api/platform/report`, `/api/platform/index` | [HTTP API](../reference/api.md) |
| Package import/promotion | Move content packages across environments | [Package Promotion](../architecture/package-promotion.md) |
| Media library / DAM | Upload allow-list, media references & usage | [Media & DAM](../architecture/media-dam.md) |

## 7. Security & governance

| Capability | Notes | Where |
|---|---|---|
| Pluggable auth | `AuthPort`; header/bearer auth plugin included | [Governance & Access](../architecture/governance-access.md) |
| RBAC & public-access rules | Permission checks, public content gating | [Governance & Access](../architecture/governance-access.md) |
| ITIL RBAC roles | Practice-aligned ITSM permissions | [ITSM / ITIL](itsm.md#rbac-itil-roles) |
| Plugin permission gating | Manifest-declared, enforced at call boundary | [Plugins & Extensibility](plugins.md) |
| Non-root containers | `uid 10001`, read-only-friendly | [Docker & Compose](../deployment/docker.md) |
| No data egress by default | Offline LLM + local storage | [Deployment Scenarios](../deployment/scenarios.md) |

---

## Architectural patterns

The platform wires a catalog of patterns — surfaced at runtime via
`GET /api/platform/capabilities`:

Repository · Unit of Work · Domain Events + Event Bus · Hexagonal Ports/Adapters ·
CQRS-lite (command vs. query services) · Specification · Strategy (LLM/embedding/
storage providers) · Plugin/SPI · Result type · State Machine (workflow) · Outbox
(webhooks) · Circuit Breaker (online LLM resilience) · Saga / Process Manager ·
Aggregate Snapshots · Composition Root.

See [C4 Model](../architecture/c4-model.md) and [Bounded Contexts](../architecture/contexts.md).

## Surfaces & APIs

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
