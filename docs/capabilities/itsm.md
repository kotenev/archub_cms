# ITSM / ITIL Suite

The ITSM plugin (`archub.itsm.service_desk`) turns ArcHub into a cloud-provider
**Service Desk** with a Jira-style **customizable workflow engine**, a real **BPMN 2.0
engine**, and the core ITIL practices: **Service Catalog**, **SLA management** and a
**CMDB** with impact analysis. It ships enabled by default and persists to SQLite or
PostgreSQL.

See the [ITSM component & sequence diagrams](../architecture/c4-model.md#level-3-components-itsm-plugin).

## Service requests (ITIL terminology)

The work item is a **Request** (`заявка`) — the ITIL record handled at the service
desk. Each request has a `type`:

| Type | ITIL practice | Default scheme |
|---|---|---|
| `incident` | Incident Management | `incident` |
| `service_request` | Request Fulfilment | `service_request` |
| `problem` | Problem Management | `problem` |
| `change` | Change Enablement | `change` |

A request carries: a workflow `status`, `priority` (low/medium/high/critical), reporter
& assignee, a **cloud resource** context (provider/service/region/resource id), an SLA
clock (`sla_response_due` / `sla_resolution_due`), a resolution, and an immutable
**history**.

## Customizable workflow engine

A `WorkflowScheme` is an explicit, runtime-built state machine — the same model Jira
exposes:

- **Statuses** in three categories: To-Do / In-Progress / Done.
- **Guarded transitions** with optional **conditions** (named predicates such as
  `is_agent`, `is_manager`, `change_approved`, `resolution_set`) and **post-functions**
  (`assign_to_actor`, `stamp_resolved_at`).
- **Global transitions** (fireable from any status — Jira's "All", e.g. *Cancel*).
- **Validation**: unreachable statuses, missing terminal state, unknown targets and
  unregistered conditions are all reported.

```python
from archub_cms.extensibility.example_plugins.itsm.workflow import WorkflowScheme, StatusCategory

scheme = (
    WorkflowScheme("incident", "Incident Management")
    .add_status("open", "Open", StatusCategory.TODO, initial=True)
    .add_status("in_progress", "In Progress", StatusCategory.IN_PROGRESS)
    .add_status("resolved", "Resolved", StatusCategory.DONE)
    .add_transition("start", "Start Progress", "in_progress", ["open"], conditions=["is_agent"])
    .add_transition("resolve", "Resolve", "resolved", ["in_progress"],
                    conditions=["resolution_set"], post_functions=["stamp_resolved_at"])
)
assert scheme.is_valid
```

## Best-practice ITIL scheme library

Ten ready-to-run, customizable schemes ship by default (`GET /api/platform/itsm/schemes`):

| Scheme | Practice | Highlights |
|---|---|---|
| `incident` | Incident Management | triage → in_progress → resolved → closed (+ cancel) |
| `major_incident` | Major Incident | team assembly → mitigation → **post-incident review** |
| `problem` | Problem Management | RCA → **known error** → RFC → resolved |
| `service_request` | Request Fulfilment | approval → fulfilment → delivered |
| `change` | Normal Change | draft → review → **CAB** → implementing → done/rolled_back |
| `standard_change` | Standard Change | pre-authorized, no CAB |
| `emergency_change` | Emergency Change | **ECAB** fast path |
| `release` | Release & Deployment | build → test → **go/no-go** → deploy |
| `event` | Event Management | triage → correlate → respond / suppress |
| `knowledge` | Knowledge Management | draft → review → published → archived |

Here is the default incident lifecycle (rendered from the engine):

```mermaid
stateDiagram-v2
  [*] --> open
  open --> triaged: Triage
  triaged --> in_progress: Start Progress
  in_progress --> pending: Wait for Customer
  pending --> in_progress: Start Progress
  in_progress --> resolved: Resolve
  resolved --> closed: Close
  resolved --> open: Reopen
  closed --> open: Reopen
  resolved --> [*]
  closed --> [*]
  cancelled --> [*]
```

## BPMN 2.0 engine

Every scheme is also a BPMN process. The engine round-trips **losslessly**:

- `to_bpmn_xml(scheme)` → layout-complete BPMN 2.0 (shapes + edges) that opens directly
  in **bpmn.io / Camunda Modeler**, with ArcHub extension attributes
  (`archub:category`, `archub:transition`, `conditions`, `postFunctions`, `global`).
- `from_bpmn_xml(xml)` → reconstructs a runnable `WorkflowScheme` (user tasks → statuses,
  sequence flows → transitions, start/end events → initial/terminal).
- `to_mermaid(scheme)` → inline state diagram for knowledge pages.

```bash
# Export a scheme as BPMN 2.0 XML
curl http://127.0.0.1:8088/api/platform/itsm/schemes/incident/bpmn

# Or as a Mermaid diagram
curl "http://127.0.0.1:8088/api/platform/itsm/schemes/incident/bpmn?format=mermaid"

# Import / customize a workflow (admin)
curl -X POST http://127.0.0.1:8088/api/platform/itsm/schemes/import-bpmn \
  -H 'Content-Type: application/json' \
  -d '{"bpmn": "<bpmn:definitions ...>", "key": "custom_incident", "name": "Custom Incident"}'
```

## Visual workflow editor (offline)

`/admin/itsm/workflow` is a visual editor for the schemes. It works **fully offline**:
the editor is shipped **as a platform plugin** (`archub.bpmn.editor`, an `EditorExt`)
whose dependency-free SVG editor and assets are served by the host itself — no CDN.

- Drag statuses, draw transitions, set the initial status, colour by category.
- **Save** posts the scheme JSON to `POST /api/platform/itsm/schemes`, which validates
  and persists it (as BPMN) through the engine.
- If the offline plugin is disabled, the page gracefully falls back to **bpmn-js**.

See [Plugins & Extensibility](plugins.md#offline-bpmn-editor-plugin) for how it is packaged.

## Service Catalog

Request-able services with a lifecycle (`planned/active/deprecated/retired`), an owner
and a linked SLA. Raising a request against a service applies that service's SLA.

```bash
curl -X POST http://127.0.0.1:8088/api/platform/itsm/catalog \
  -H 'Content-Type: application/json' \
  -d '{"name": "Managed PostgreSQL", "category": "database", "sla_id": "sla-gold"}'
```

## SLA management

Named agreements (`Gold`, `Silver`, …) declaring **response** and **resolution**
minutes per priority. The chosen SLA computes a request's due times at creation; the
queue summary reports breaches.

```bash
curl -X POST http://127.0.0.1:8088/api/platform/itsm/sla \
  -H 'Content-Type: application/json' \
  -d '{"name": "Gold", "targets": {"critical": [15, 240], "high": [30, 480]}}'
```

## CMDB & impact analysis

Configuration Items (CIs: business services, applications, servers, databases,
load balancers, …) and typed relationships (`depends_on`, `runs_on`, `connected_to`,
…). **Impact analysis** answers the incident/change manager's core question:

```bash
# What is affected if this database fails, and what does it depend on?
curl http://127.0.0.1:8088/api/platform/itsm/cmdb/items/<ci_id>/impact
```

A request can be linked to a service and CIs; `GET /requests/{key}/impact` then shows
the blast radius.

## RBAC (ITIL roles)

Identity groups map to ITIL roles (requester, service desk agent, incident/problem/
change manager, CAB member, release manager, service owner, auditor, ITSM admin), each
granting ITSM permissions (`itsm:read`, `:request:create`, `:transition`, `:assign`,
`:approval`, `:manage`, `:admin`). Endpoints are permission-gated; the workflow
`actor_role` flows into transition conditions.

```bash
curl http://127.0.0.1:8088/api/platform/itsm/rbac/roles
```

## Storage backends

Default is SQLite (shared ArcHub database, audited through the
[plugin platform adapter](../architecture/plugin-platform-adapter.md)). Switch the
plugin to PostgreSQL with a setting or environment variable:

```bash
export ARCHUB_ITSM_PG_DSN=postgresql://archub:archub@localhost:5432/archub_itsm
```

Requests **and** all reference data (catalog, SLA, CMDB, persisted BPMN schemes) then
live in PostgreSQL. See [Docker deployment](../deployment/docker.md#compose-itsm-on-postgresql).

## End-to-end example

```bash
BASE=http://127.0.0.1:8088/api/platform/itsm

# 1. Define an SLA and a catalog service that uses it
SLA=$(curl -s -X POST $BASE/sla -H 'Content-Type: application/json' \
  -d '{"name":"Gold","targets":{"high":[10,60]}}' | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
SVC=$(curl -s -X POST $BASE/catalog -H 'Content-Type: application/json' \
  -d "{\"name\":\"Managed PG\",\"category\":\"database\",\"sla_id\":\"$SLA\"}" | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 2. Raise an incident against the service (Gold SLA is applied automatically)
REQ=$(curl -s -X POST $BASE/requests -H 'Content-Type: application/json' \
  -d "{\"type\":\"incident\",\"summary\":\"pg down\",\"priority\":\"high\",\"service_id\":\"$SVC\"}")
echo "$REQ"   # → key REQ-1, status open, sla_resolution_due = created_at + 3600s

# 3. Work it through the workflow
curl -s -X POST $BASE/requests/REQ-1/transitions -H 'Content-Type: application/json' \
  -d '{"transition":"triage","actor_role":"agent"}'
```

See the [HTTP API reference](../reference/api.md#itsm-api) for the full endpoint list.
