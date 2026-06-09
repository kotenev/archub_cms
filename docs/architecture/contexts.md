# ArcHub platform architecture — bounded contexts

ArcHub started as a single 8,582-line `ArcHubCMSService` (`services/cms.py`) and has
been refactored into a DDD platform: 20 bounded contexts on a shared kernel +
infrastructure, an executable plugin runtime, and a composition root. The legacy
service is untouched and remains the SQLite persistence engine that context
adapters delegate to (pinned by `tests/test_cms_characterization.py`).

## Layers

```
kernel/            EventBus, UnitOfWork, Result, Specification
infrastructure/    db/ (connection + migrations), sqlite/ + plugins/ adapters
domain/<context>/  aggregates, value objects, domain events, repository PORTS
application/<ctx>_service.py   CQRS-lite services; emit events; orchestrate repos
extensibility/     PluginHost + SPI (25 extension-point types) + platform adapter
web/platform_routes.py   /api/platform/* HTTP surface
application/platform.py   ArcHubPlatform composition root + capabilities()
```

## Bounded contexts (20)

| Context | Domain | Application service(s) | Key API prefix |
|---|---|---|---|
| content | `ContentNode` aggregate | `content_service` | (internal) |
| knowledge | spaces/docs, RAG | `knowledge` | `/knowledge/*` |
| collaboration | comments/mentions/reactions | `collaboration_service` | `/collaboration/*` |
| modeling | content types/fields | `modeling_service` | `/modeling/*` |
| delivery | sitemap/feed/tags/redirects | `delivery_read_service` | `/delivery/*` |
| versioning | history + diff + restore | `versioning_service` | `/versioning/*` |
| governance | RBAC + access policy | `governance_service` | `/governance/*` |
| workflow | review/approval state machine | `workflow_service` | `/workflow/*` |
| media | assets + pluggable storage | `media_service` | `/media/*`, `/storage/*` |
| packaging | export/import bundles | `packaging_service` | `/packaging/*` |
| graph | backlinks/metrics/canvas | `graph_service` | `/graph/*` |
| runtime | RAG export/snapshot | `runtime_service` | `/runtime/*` |
| localization | culture variants + dictionary | `localization_service` | `/localization/*` |
| analytics | health/audit/activity | `analytics_service` | `/analytics/*` |
| webhooks | Outbox + notification channels | `webhooks_service` | `/webhooks/*` |
| search | federated + faceted | `search_service` | `/search` |
| subscriptions | watchers + derived inbox | `subscription_service` | `/subscriptions/*` |
| blueprints | starter content templates | `blueprint_service` | `/blueprints/*` |
| locks | edit reservation | `lock_service` | `/locks/*` |
| trash | recycle bin | `trash_service` | `/trash/*` |

Plus: **agentic** tool-use answering (`agent_service`, `/knowledge/agent-answer`) and
the **composition root** (`ArcHubPlatform`, `/capabilities`, `/index`).

## Architectural patterns

Repository · Unit of Work · Domain Events + in-process Event Bus · Hexagonal
Ports/Adapters · CQRS-lite · Specification · Strategy (LLM/embedding/storage
providers) · Plugin/SPI · Result · State Machine (workflow) · Outbox (webhooks) ·
Composition Root.

## Plugin extension points (25)

EventHook · Search · Renderer · Macro · Importer · Exporter · LLMTool · Auth ·
Storage · Notification · Theme · ScheduledJob · AnalyticsProvider ·
WorkflowAction · ContentTransformer · SearchIndexer · SecurityPolicy · Editor ·
Connector · ChatHandler · DashboardWidget · ExportFormat · ImportFormat ·
LiveEdit · PageAction — plus declarative manifest capabilities. Two runtimes:
in-process Python entrypoints and HTTP/sandboxed tools. Lifecycle
(enable/disable/configure) is handled by `plugin_management_service`; persistent
plugin state is written through `PluginPlatformAdapter` and audited in
`archub_plugin_audit`.

## Legacy facade consolidation map

The original thin `application/*.py` facades are **superseded** by the new context
services (which add domain aggregates, invariants and events). The legacy facades
are retained for back-compat (and still exercised by
`tests/test_architecture_facades.py`); prefer the new contexts:

| Legacy facade | Canonical replacement |
|---|---|
| `application/modeling.py` | `application/modeling_service.py` |
| `application/packages.py` | `application/packaging_service.py` |
| `application/governance.py` | `application/governance_service.py` |
| `application/versioning.py` | `application/versioning_service.py` |
| `application/webhooks.py` | `application/webhooks_service.py` |

`application/delivery.py` (response *projection*), `application/media.py` (upload
*policy*) and `application/publishing.py` (publish actions) cover concerns distinct
from their similarly-named new contexts and are **not** deprecated.

## Offline + online LLM

Offline by default (zero-dependency hashing embedder + extractive provider); online
via OpenAI-compatible chat/embeddings when `ARCHUB_LLM_BASE_URL`/`ARCHUB_LLM_API_KEY`
are set. Hybrid lexical+semantic+plugin ranking; agentic tool use over `LLMToolExt`.
