# ArcHub Core Platform

ArcHub is moving from a CMS package with extensions to a platform where every
major subsystem is represented as an installable module. The CMS is now modeled
as the core plugin `archub.cms.core`; external CMS features remain ordinary
plugins.

## Core Plugin Model

Core plugins are built-in manifests with:

- `core: true`
- `runtime: "rust"`
- `language: "rust"`
- `rust_crate`: the Rust crate that owns the target implementation
- `provides`: stable capability contracts exposed to the platform

The current Python application remains the compatibility shell, FastAPI host,
and migration harness. Rust crates define the new core contracts and will absorb
behavior module by module.

## Core Modules

| Module | Capability | Rust crate | Provides |
|---|---|---|---|
| `archub.platform.kernel` | `platform_module` | `archub-core` | events, mediator, saga, health |
| `archub.cms.core` | `cms` | `archub-cms-core` | content, modeling, publishing, delivery, runtime |
| `archub.knowledge.spaces` | `knowledge` | `archub-knowledge-core` | spaces, tags, graph, bookmarks, templates |
| `archub.media.assets` | `media` | `archub-media-core` | assets, DAM, blob store |
| `archub.collaboration.threads` | `collaboration` | `archub-collaboration-core` | comments, mentions, reactions |
| `archub.collaboration.live-edit` | `live_edit` | `archub-collaboration-core` | presence, conflict detection |
| `archub.adapter.sqlite` | `adapter` | `archub-adapters` | SQLite repositories |
| `archub.adapter.plugin-store` | `adapter` | `archub-adapters` | plugin store, plugin audit |
| `archub.rest.platform` | `rest_api` | `archub-rest-api` | platform/module REST surface |
| `archub.search.lexical` | `search` | `archub-search-core` | lexical search, facets, index |
| `archub.llm.extractive` | `llm_provider` | `archub-llm-core` | offline grounded answers |
| `archub.llm.openai-compatible` | `llm_provider` | `archub-llm-core` | online chat completions |
| `archub.workflow.publish` | `workflow` | `archub-workflow-core` | approval, schedule, publish |
| `archub.governance.rbac` | `governance` | `archub-governance-core` | RBAC, ITIL roles |
| `archub.compliance.audit` | `compliance` | `archub-governance-core` | immutable audit trail |
| `archub.automation.maintenance` | `automation` | `archub-automation-core` | scheduler, maintenance jobs |
| `archub.notification.webhook` | `notification` | `archub-automation-core` | signed webhook delivery |
| `archub.analytics.health` | `analytics` | `archub-automation-core` | content health scoring |

CMS-adjacent plugins such as Markdown import, vault export, runtime sync,
structured editor, and content macros live in `archub-cms-core`.

## Rust Workspace

```text
Cargo.toml
rust/
  archub-core/       core plugin traits and health contracts
  archub-cms-core/   CMS content and publishing core skeleton
  archub-adapters/   storage/audit/plugin-store adapter traits
  archub-rest-api/   REST route descriptors and API module contract
  archub-search-core/
  archub-llm-core/
  archub-workflow-core/
  archub-governance-core/
  archub-automation-core/
  archub-knowledge-core/
  archub-media-core/
  archub-collaboration-core/
```

The workspace intentionally avoids third-party crates at this stage. This keeps
`cargo check --workspace` offline and makes the migration contract explicit
before replacing Python service internals.

## Workspace Coverage

The Python compatibility shell inventories `Cargo.toml` and exposes
`core_plugins.rust_workspace` from `/api/platform/capabilities`. A core plugin is
considered covered when its manifest has `runtime: "rust"` and `rust_crate`
points to a workspace crate. CI tests keep `missing_total` at zero.

Dedicated read models are also available:

- `GET /api/platform/core-plugins`
- `GET /api/platform/core-plugins/rust-workspace`

## Migration Rule

New platform behavior should be introduced as a core or external module
manifest first, then backed by Rust code where appropriate. Python routes and
services should call through compatibility adapters until the corresponding
Rust implementation is feature-complete.
