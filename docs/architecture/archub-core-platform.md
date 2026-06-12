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
| `archub.adapter.sqlite` | `adapter` | `archub-adapters` | SQLite repositories |
| `archub.adapter.plugin-store` | `adapter` | `archub-adapters` | plugin store, plugin audit |
| `archub.rest.platform` | `rest_api` | `archub-rest-api` | platform/module REST surface |

Other built-in capabilities such as search, LLM providers, governance, workflow,
analytics, and export/import are also represented as Rust core manifests so they
can be packaged to the marketplace consistently.

## Rust Workspace

```text
Cargo.toml
rust/
  archub-core/       core plugin traits and health contracts
  archub-cms-core/   CMS content and publishing core skeleton
  archub-adapters/   storage/audit/plugin-store adapter traits
  archub-rest-api/   REST route descriptors and API module contract
```

The workspace intentionally avoids third-party crates at this stage. This keeps
`cargo check --workspace` offline and makes the migration contract explicit
before replacing Python service internals.

## Migration Rule

New platform behavior should be introduced as a core or external module
manifest first, then backed by Rust code where appropriate. Python routes and
services should call through compatibility adapters until the corresponding
Rust implementation is feature-complete.
