# ArcHub Platform

> A standalone, embeddable **knowledge, content & ITSM platform** for Python/FastAPI
> hosts — three products in one Apache-2.0 package (`archub_cms`), on a hexagonal/DDD
> core with a real plugin runtime, that runs offline on a laptop and scales to a
> PostgreSQL-backed cluster.

ArcHub unifies what teams normally buy as **three separate SaaS subscriptions**:

| You usually buy… | ArcHub ships it as… |
|---|---|
| Confluence / Notion / Wiki.js | **Enterprise Knowledge Base** with offline **and** online RAG |
| Strapi / Contentful / Umbraco Heartcore | **Headless CMS & Content Builder** with a delivery API |
| ServiceNow / Jira Service Management | **ITSM/ITIL suite** with a BPMN workflow engine |

…sharing one data model, one auth boundary, one plugin runtime and one deployment
artifact. No per-seat pricing, no vendor lock-in, no data leaving your perimeter.

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting Started](getting-started.md)** — install and run in
  one command.
- :material-lightbulb-on: **[Use Cases](use-cases.md)** — the scenarios ArcHub is built
  for.
- :material-scale-balance: **[Comparison](comparison.md)** — ArcHub vs Confluence,
  Wiki.js, Strapi, ServiceNow & more.
- :material-shape: **[Capabilities](capabilities/index.md)** — the full feature catalog.
- :material-server: **[Deployment](deployment/scenarios.md)** — from laptop to cluster.
- :material-sitemap: **[Architecture](architecture/c4-model.md)** — PlantUML C4 model.

</div>

## What is ArcHub?

ArcHub is **not** a hosted SaaS and **not** a monolithic app you fork. It is a Python
library (`pip install archub_cms`) that you can:

- **run as a batteries-included app** — `create_archub_app()` boots an ASGI server,
  seeds demo content and mounts every surface; or
- **embed router-by-router** into an existing FastAPI product — mount only the CMS, only
  the knowledge API, or only ITSM.

Everything host-specific (authentication, templating, storage, LLM, cache invalidation,
audit) lives behind **Protocol ports** (`AuthPort`, `TemplatePort`, `LLMProviderPort`,
`EmbeddingPort`, `SearchPort`, `CacheInvalidationPort`, `AuditSink`, …), so ArcHub adapts
to your environment instead of dictating it.

### Design principles

1. **Offline-first.** The default stack has *zero required services*: an embedded SQLite
   database and a fully offline-extractive LLM. No network, no API keys, no Node.js. This
   makes ArcHub viable for air-gapped, regulated and on-premise environments where SaaS
   knowledge tools are forbidden.
2. **Progressive enhancement.** Bring PostgreSQL when you need concurrency; bring an
   OpenAI-compatible endpoint when you want generative answers. A **circuit breaker**
   degrades the online LLM back to offline automatically.
3. **Hexagonal & DDD.** Layered `domain → application → services → web`; bounded contexts;
   ports/adapters; CQRS-lite; domain events on an in-process bus. Host code never leaks
   into the core.
4. **Genuinely extensible.** A real plugin **host** loads in-process Python *and*
   HTTP/sandboxed external plugins (including PHP modules), gated by manifest permissions,
   over 25+ typed extension points.

## The three pillars

### :material-book-open-variant: Headless CMS & Content Builder
Umbraco-style **document types**, reusable **data types** and **templates**; a
hierarchical content tree with **draft / publish / unpublish / trash / restore**; full
**version history**, **preview/share tokens**, **redirects**, **domains**, **cultures**,
**variants** and **segments**; a **Content Builder** block registry with strict
normalization and HTML rendering; **blueprints**, **edit locks** and a **recycle bin**;
and a published **delivery API** (content, tree, search, tags, RSS, sitemap) with cache
headers and runtime/RAG exports. → [Content Builder](content-builder.md) ·
[Delivery API](delivery-api.md)

### :material-brain: Enterprise Knowledge Base (offline + online LLM)
**Hybrid lexical + semantic search** over SQLite **FTS5** (BM25, porter stemming); a
fully **offline-extractive** LLM by default and an **OpenAI-compatible** online provider
behind a **circuit breaker**; **agentic, tool-using** answering; **backlinks / graph**
read model (Obsidian-style); and **Obsidian vault export**. →
[Enterprise Knowledge Platform](architecture/enterprise-knowledge-platform.md)

### :material-ticket-confirmation: ITSM / ITIL suite
A cloud **Service Desk** (incidents, service requests, problems, changes) with a
**Jira-style customizable workflow engine**, a real **BPMN 2.0 engine** (lossless
import/export + Mermaid, plus an **offline visual editor**), **10 best-practice ITIL
workflow schemes**, and the core practices — **Service Catalog**, **SLA management** and a
**CMDB** with impact/blast-radius analysis — over SQLite **or** PostgreSQL, with ITIL
**RBAC** roles. → [ITSM / ITIL](capabilities/itsm.md)

### :material-puzzle: Extensibility runtime (the glue)
A plugin **host** with in-process (Python) and HTTP/sandboxed/external runtimes, **25+
extension points** (renderer, macro, search, LLM tool, importer/exporter, editor,
storage, auth, notification, workflow…), **manifest permissions**, a per-plugin **config
store**, an **audited platform persistence adapter** and a **module marketplace** packager.
Even UI ships as plugins — the offline BPMN editor and the PHP **Wiki** and
**OurLifeOrganized** modules are plugins. → [Plugins & Extensibility](capabilities/plugins.md)

## Who is it for?

| Audience | Why ArcHub |
|---|---|
| **Platform / product engineers** | Drop a CMS, knowledge base or service desk into an existing FastAPI product without standing up three new services. |
| **Regulated / air-gapped orgs** | Full knowledge + RAG with no data egress, no API keys, no external dependencies. |
| **Internal IT / SRE teams** | An ITIL service desk with a customizable BPMN workflow engine, on infrastructure you already run. |
| **Knowledge / docs teams** | Confluence/Wiki.js-class spaces, backlinks and search, self-hosted under Apache-2.0. |
| **Solution builders / ISVs** | A white-label, plugin-extensible platform with no per-seat licensing. |

## At a glance

| | |
|---|---|
| **License** | Apache-2.0 |
| **Language / runtime** | Python 3.11+ (developed on 3.14), ASGI / FastAPI |
| **Default storage** | Embedded SQLite (+ FTS5) — zero services |
| **Optional storage** | PostgreSQL (ITSM and shared multi-replica deployments) |
| **Default AI** | Offline-extractive (no network, no keys) |
| **Optional AI** | Any OpenAI-compatible endpoint, with circuit breaker |
| **Packaging** | One `pip` package; embed routers or run the app factory |
| **Containers** | Dockerfile + Compose, non-root, healthcheck, `/data` volume |
| **Extensibility** | Plugin host: in-process Python + HTTP/external (PHP) modules |

## Surfaces

| Surface | Path |
|---|---|
| CMS backoffice | `/admin/archub` |
| Platform dashboard | `/admin/platform` |
| ITSM Service Desk | `/admin/itsm` |
| Visual BPMN editor | `/admin/itsm/workflow` |
| Published site | `/cms` |
| Platform API | `/api/platform/*` |
| ITSM API | `/api/platform/itsm/*` |
| OpenAPI / Swagger | `/api/docs` |

## Where to next

- New here? → **[Getting Started](getting-started.md)** then **[Use Cases](use-cases.md)**.
- Evaluating? → **[Comparison](comparison.md)** and the **[Capability catalog](capabilities/index.md)**.
- Deploying? → **[Deployment scenarios](deployment/scenarios.md)**.
- Building on it? → **[Plugins](capabilities/plugins.md)** and the
  **[HTTP API reference](reference/api.md)**.

ArcHub is released under **Apache-2.0**.
