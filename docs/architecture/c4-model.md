# C4 Architecture Model

This page documents the ArcHub platform with the [C4 model](https://c4model.com/)
(Context → Container → Component) using **PlantUML C4**. The diagrams render through
the configured PlantUML server; the same sources are committed under
`docs/diagrams/c4/*.puml` so you can render them offline with the `plantuml` CLI:

```bash
plantuml -tsvg docs/diagrams/c4/*.puml
```

ArcHub is a single, embeddable Python package (`archub_cms`) exposing a FastAPI app.
It is organized as a **hexagonal + DDD** core (bounded-context application services
behind ports), a **plugin runtime** (in-process and HTTP/sandboxed), and a set of
**productized capabilities** — headless CMS, enterprise knowledge base with offline +
online RAG, and a full **ITSM/ITIL** suite (Service Desk, BPMN workflow engine, Service
Catalog, SLA and CMDB).

---

## Level 1 — System Context

```plantuml
@startuml
!include <C4/C4_Context>
LAYOUT_WITH_LEGEND()
title System Context — ArcHub Platform

Person(editor, "Content Editor", "Authors documents, models content, publishes")
Person(agent_user, "ITSM Agent / Manager", "Logs and works incidents, changes, problems; approves; models workflows")
Person(requester, "Requester / Customer", "Raises service requests, reads the knowledge base")
Person(visitor, "Public Visitor", "Reads published content via the delivery API")
Person(plugin_dev, "Plugin Developer", "Ships manifests + extensions on the SPI")

System(archub, "ArcHub Platform", "FastAPI app: headless CMS, knowledge base + RAG, ITSM/ITIL suite, plugin runtime")

System_Ext(host, "Host FastAPI App", "Optional: mounts ArcHub routers / embeds the package")
System_Ext(llm, "LLM & Embedding Provider", "OpenAI-compatible endpoint (online); offline-extractive when absent")
System_Ext(pg, "PostgreSQL", "Optional storage backend for the ITSM plugin")
System_Ext(integrations, "Integrations", "Webhooks, Slack/Jira/GitHub connectors, cloud monitoring alerts")
System_Ext(bpmn_tools, "BPMN Tooling", "bpmn.io / Camunda Modeler — import/export BPMN 2.0")

Rel(editor, archub, "Authors & publishes", "HTTPS / backoffice")
Rel(agent_user, archub, "Works tickets, models BPMN workflows", "HTTPS / /admin/itsm")
Rel(requester, archub, "Raises requests, reads KB", "HTTPS")
Rel(visitor, archub, "Reads published content", "HTTPS / delivery API")
Rel(plugin_dev, archub, "Publishes plugins (manifest + entrypoint)", "Python / HTTP")

Rel(archub, llm, "Grounded answers & embeddings", "HTTPS")
Rel(archub, pg, "Persists ITSM data (optional)", "SQL")
Rel(archub, integrations, "Emits signed events, syncs", "HTTPS")
Rel(archub, bpmn_tools, "Exchanges BPMN 2.0 XML", "file / paste")
Rel(host, archub, "Embeds routers & ports", "Python")
@enduml
```

---

## Level 2 — Containers

The whole platform ships as one process, but it is cleanly layered. The "containers"
below are logical runtime units inside the `archub_cms` package.

```plantuml
@startuml
!include <C4/C4_Container>
LAYOUT_WITH_LEGEND()
title Container View — ArcHub Platform (single FastAPI process)

Person(editor, "Content Editor")
Person(agent_user, "ITSM Agent / Manager")
Person(visitor, "Public Visitor")

System_Boundary(archub, "ArcHub Platform") {
  Container(web, "Web Layer", "FastAPI routers", "routes, platform_routes, collaboration_routes, admin_routes, itsm_routes (+ HTML admin/editor)")
  Container(platform_root, "ArcHubPlatform", "Composition root", "Wires bounded-context application services & architectural patterns")
  Container(services, "Bounded-Context Services", "DDD application layer", "content, knowledge, delivery, modeling, governance, workflow, media, search, …")
  Container(plugin_host, "Plugin Host", "Extensibility runtime", "Discovers manifests, permission-gates, loads in-process & HTTP plugins; classifies 25+ extension points")
  Container(adapter, "Plugin Platform Adapter", "Capability boundary", "Audited SQLite/PostgreSQL stores + document repositories handed to plugins")
  Container(itsm, "ITSM Plugin", "Service Desk + ITIL", "ServiceDesk, BPMN engine, Catalog, SLA, CMDB")
  Container(editor_plugin, "Offline BPMN Editor Plugin", "EditorExt + static assets", "Dependency-free SVG workflow editor (no CDN)")
  ContainerDb(sqlite, "SQLite", "Embedded DB", "Content tree, versions, FTS5 index, plugin config, ITSM data")
  ContainerDb(fs, "Filesystem", "Runtime exports", "RAG materials, vault exports, BPMN")
}

System_Ext(llm, "LLM / Embedding Provider")
ContainerDb_Ext(pg, "PostgreSQL", "Optional ITSM backend")

Rel(editor, web, "Backoffice & APIs", "HTTPS")
Rel(agent_user, web, "/api/platform/itsm/*, /admin/itsm", "HTTPS")
Rel(visitor, web, "Delivery API", "HTTPS")

Rel(web, platform_root, "Resolves services")
Rel(web, itsm, "Drives Service Desk / schemes", "via plugin host")
Rel(platform_root, services, "Owns & exposes")
Rel(services, plugin_host, "Fires domain events, calls hooks")
Rel(plugin_host, itsm, "Loads & runs")
Rel(plugin_host, editor_plugin, "Loads (EditorExt + assets)")
Rel(itsm, adapter, "Requests audited repositories")
Rel(adapter, sqlite, "Reads/writes", "SQL")
Rel(adapter, pg, "Reads/writes (optional)", "SQL")
Rel(services, sqlite, "Reads/writes", "SQL")
Rel(services, fs, "Exports")
Rel(services, llm, "Answers & embeddings", "HTTPS")
@enduml
```

---

## Level 3 — Components (ITSM plugin)

A zoom into the ITSM/ITIL capability — the workflow/BPMN engine and the ITIL
registries — and how the offline editor and REST API drive it.

```plantuml
@startuml
!include <C4/C4_Component>
LAYOUT_WITH_LEGEND()
title Component View — ITSM Plugin & BPMN Engine

Container(web, "itsm_routes", "FastAPI", "/api/platform/itsm/* + /admin/itsm HTML")
Container(editor_plugin, "Offline BPMN Editor", "EditorExt + JS/CSS assets")
ContainerDb(store, "Platform Stores", "SQLite / PostgreSQL", "audited, via the adapter")

Component(itsm_service, "ItsmService", "Facade", "Composes the desk + ITIL registries; imports/persists BPMN schemes; SLA-aware request logging; impact analysis")
Component(desk, "ServiceDesk", "Application facade", "Create/transition/assign requests; queue & SLA summary")
Component(engine, "Workflow Engine", "State machine", "WorkflowScheme: statuses, guarded transitions, conditions, post-functions; validation")
Component(bpmn, "BPMN Engine", "Serializer/parser", "to_bpmn_xml / from_bpmn_xml — lossless BPMN 2.0 round-trip + Mermaid")
Component(schemes, "ITIL Scheme Library", "Defaults", "incident, major_incident, problem, request, normal/standard/emergency change, release, event, knowledge")
Component(catalog, "Service Catalog", "Registry", "Request-able services + lifecycle + linked SLA")
Component(sla, "SLA Registry", "Registry", "Per-priority response/resolution targets → SlaPolicy")
Component(cmdb, "CMDB", "Registry + graph", "Configuration items, relationships, impact analysis")
Component(repos, "Repositories", "Adapters", "Request repository + document repositories (catalog/SLA/CMDB/schemes/links)")

Rel(web, itsm_service, "Calls")
Rel(web, desk, "Calls")
Rel(editor_plugin, web, "Loads schemes, POST /schemes & /schemes/import-bpmn", "fetch")
Rel(itsm_service, desk, "Wraps")
Rel(itsm_service, catalog, "Resolves service → SLA")
Rel(itsm_service, sla, "Computes due times")
Rel(itsm_service, cmdb, "Impact analysis")
Rel(itsm_service, bpmn, "Import / persist schemes")
Rel(desk, engine, "Applies transitions")
Rel(desk, schemes, "Default scheme per type")
Rel(engine, bpmn, "Serialize / parse")
Rel(desk, repos, "Persists requests")
Rel(catalog, repos, "Documents")
Rel(sla, repos, "Documents")
Rel(cmdb, repos, "Documents")
Rel(itsm_service, repos, "Scheme & impact-link documents")
Rel(repos, store, "Audited reads/writes", "SQL")
@enduml
```

---

## Runtime sequence — raise an incident under an SLA

```plantuml
@startuml
!include <C4/C4_Sequence>
title Sequence — POST /api/platform/itsm/requests (service-linked)

Person(agent, "Agent")
Container(api, "itsm_routes")
Component(svc, "ItsmService")
Component(cat, "Service Catalog")
Component(sla, "SLA Registry")
Component(desk, "ServiceDesk")
ContainerDb(db, "Platform Store")

Rel(agent, api, "POST /requests {type, summary, service_id}")
Rel(api, svc, "log_request(service_id=…)")
Rel(svc, cat, "find(service_id) → sla_id")
Rel(svc, sla, "policy_for(sla_id) → SlaPolicy")
Rel(svc, desk, "create_request(sla=policy)")
Rel(desk, db, "persist request + history")
Rel(svc, db, "persist impact link (service + CIs)")
Rel(api, agent, "201 {key, status, sla_*_due}")
@enduml
```

See [ITSM / ITIL](../capabilities/itsm.md) for the full capability documentation and
[Bounded Contexts](contexts.md) for the CMS/knowledge core.
