# HTTP API Reference

Interactive docs are always available at `/api/docs` (Swagger) and `/api/redoc`. This
page summarizes the route catalog. All paths are relative to the app root.

## Surfaces

| Group | Prefix |
|---|---|
| Public delivery + backoffice | `/`, `/cms`, `/admin/archub` |
| Platform API | `/api/platform` |
| Collaboration API | `/api/platform/collaboration` |
| ITSM API | `/api/platform/itsm` |
| ITSM HTML | `/admin/itsm`, `/admin/itsm/workflow` |

## Platform API (selected)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/platform/capabilities` | Self-describing capability + pattern catalog |
| GET | `/api/platform/index` | Route browser grouped by context |
| GET | `/api/platform/report` | Platform + plugin runtime report |
| GET | `/api/platform/plugins` | Loaded plugins + classified extensions |
| GET | `/api/platform/plugins/catalog` | Manifest catalog |
| POST | `/api/platform/plugins/{id}/enable` · `/disable` · `/settings` | Manage a plugin |
| POST | `/api/platform/plugins/install/file` | Install a plugin/module from directory, manifest, ZIP or TAR |
| GET | `/api/platform/plugins/marketplace` | Read a marketplace repository |
| POST | `/api/platform/plugins/marketplace/install` | Install from a marketplace repository |
| GET | `/api/platform/modules/marketplace` | Module marketplace catalog alias |
| POST | `/api/platform/modules/marketplace/install` | Module marketplace install alias |
| GET | `/api/platform/extensions` | Macros, renderers, importers, tools, … |
| POST | `/api/platform/render` | Run renderers + expand macros |
| POST | `/api/platform/tools/{name}/run` | Invoke an LLM tool |
| GET/POST | `/api/platform/search` · `/search/fts` | Federated + FTS5 search |
| GET | `/api/platform/knowledge/graph` | Backlinks / graph read model |
| POST | `/api/platform/knowledge/agent-answer` | Agentic, tool-using RAG answer |
| GET | `/api/platform/analytics/health` · `/dashboard` | Content health & analytics |
| GET/POST | `/api/platform/locks`, `/trash`, `/blueprints` | Edit locks, recycle bin, blueprints |

## ITSM API

Base prefix `/api/platform/itsm`. Permissions in brackets (see
[ITSM RBAC](../capabilities/itsm.md#rbac-itil-roles)).

### Requests

| Method | Path | Perm | Purpose |
|---|---|---|---|
| GET | `/requests` | read | List/filter (`type`, `status`, `assignee`) |
| POST | `/requests` | create | Raise a request (`type`, `summary`, `priority`, `service_id`, `sla_id`, `ci_ids`, …) |
| GET | `/requests/{key}` | read | Get a request |
| GET | `/requests/{key}/transitions` | read | Available transitions |
| POST | `/requests/{key}/transitions` | transition | Apply a transition (`transition`, `resolution`, `approved`) |
| POST | `/requests/{key}/assign` | assign | Assign (`assignee`) |
| GET | `/requests/{key}/impact` | read | Linked service + CIs + blast radius |
| GET | `/queue` | read | Queue counts + SLA breaches |
| GET | `/report` | read | Combined ITSM report |

### Workflow schemes & BPMN engine

| Method | Path | Perm | Purpose |
|---|---|---|---|
| GET | `/schemes` | read | List schemes (the ITIL library) |
| GET | `/schemes/{key}` | read | Scheme detail (statuses, transitions, validity) |
| GET | `/schemes/{key}/bpmn` | read | BPMN 2.0 XML (or `?format=mermaid`) |
| POST | `/schemes` | admin | Register a scheme from JSON (offline editor save) |
| POST | `/schemes/import-bpmn` | admin | Import/customize from BPMN 2.0 XML |
| DELETE | `/schemes/{key}` | admin | Delete a custom scheme (built-ins are protected) |

### Service Catalog

| Method | Path | Perm |
|---|---|---|
| GET/POST | `/catalog` | read / manage |
| GET/PUT/DELETE | `/catalog/{service_id}` | read / manage |

### SLA

| Method | Path | Perm |
|---|---|---|
| GET/POST | `/sla` | read / manage |
| GET/PUT/DELETE | `/sla/{sla_id}` | read / manage |

### CMDB

| Method | Path | Perm |
|---|---|---|
| GET/POST | `/cmdb/items` | read / manage |
| GET/PUT/DELETE | `/cmdb/items/{ci_id}` | read / manage |
| GET | `/cmdb/items/{ci_id}/impact` | read |
| GET/POST | `/cmdb/relationships` | read / manage |
| DELETE | `/cmdb/relationships/{relationship_id}` | manage |

### RBAC

| Method | Path | Perm |
|---|---|---|
| GET | `/rbac/roles` | read |

## Error model

| Status | Meaning |
|---|---|
| `401` | Authentication required |
| `403` | Missing ITSM permission |
| `404` | Unknown request / scheme / catalog / SLA / CI |
| `409` | Illegal workflow transition or unmet condition; deleting a built-in scheme |
| `422` | Validation error (e.g. invalid BPMN/scheme → `{"detail": {"problems": [...]}}`) |
| `503` | ITSM plugin disabled |

## Authentication

Endpoints resolve identity via the loaded auth plugins (e.g. `header_auth`: a
`Authorization: Bearer <token>`, or `X-ArcHub-User` / `X-ArcHub-Groups` /
`X-ArcHub-Admin` headers). Demo tokens (`demo-itsm-agent-token`,
`demo-itsm-change-manager-token`, `demo-itsm-admin-token`, …) map to ITIL roles. With
no credentials the dev default identity is an admin.
