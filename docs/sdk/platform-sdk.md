# ArcHub Platform SDK Release

ArcHub Platform SDK 1.0.0 is a beta developer kit for integrating with ArcHub
platform APIs, creating plugins and automating marketplace/module workflows.

## Release Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Python SDK | `sdk/python` | Dependency-free typed HTTP client and plugin manifest builder. |
| OpenAPI subset | `sdk/openapi/archub-platform-sdk.openapi.yaml` | Stable SDK-facing platform API contract. |
| Release manifest | `sdk/release/archub-sdk-1.0.0.json` | Machine-readable SDK release metadata. |
| CLI | `archub-sdk-release` | Prints SDK release summary or JSON. |

## Technology Stack

- Platform: FastAPI, SQLite/PostgreSQL adapters, Rust core plugin workspace.
- SDK language: Python 3.11+.
- Transport: HTTP JSON over `urllib.request`; no runtime dependencies.
- Plugin model: manifest, Python, HTTP/external services, Rust core modules.
- Documentation: MkDocs Material, OpenAPI 3.1, PlantUML.

## Install

```bash
python -m pip install ./sdk/python
```

## Basic Usage

```python
from archub_platform_sdk import ArcHubClient, PluginManifest

client = ArcHubClient("http://127.0.0.1:8088")
caps = client.capabilities()

manifest = PluginManifest(
    plugin_id="acme.wiki.bridge",
    name="Acme Wiki Bridge",
    version="1.0.0",
    capability="connector",
    runtime="external",
    entrypoint="https://wiki.example.test/api/arc-tool",
)
payload = manifest.to_json()
```

## API Coverage

| Group | SDK methods | HTTP endpoints |
|---|---|---|
| Platform | `capabilities()`, `platform_index()` | `/api/platform/capabilities`, `/api/platform/index` |
| Core plugins | `core_plugins()`, `rust_workspace()` | `/api/platform/core-plugins`, `/api/platform/core-plugins/rust-workspace` |
| Plugins | `plugin_catalog()`, `enable_plugin()`, `disable_plugin()` | `/api/platform/plugins/*` |
| Marketplace | `marketplace()`, `install_from_marketplace()` | `/api/platform/modules/marketplace*` |
| Delivery | `delivery_tree()`, `delivery_content()`, `delivery_search()` | `/cms/api/*` |
| Knowledge | `knowledge_search()`, `knowledge_answer()` | `/api/platform/knowledge/*` |
| Runtime | `runtime_status()`, `runtime_export()` | `/api/platform/runtime/*` |

## Functional Capabilities

- Read platform capabilities, bounded contexts, plugin runtime and core plugin
  Rust workspace coverage.
- Inspect and manage plugins/modules through the platform management API.
- Read marketplace repositories and install module distributions.
- Query published delivery content and search indexes.
- Run knowledge search and grounded answers against the knowledge base.
- Trigger runtime exports for RAG/offline consumers.
- Generate validated `plugin.json` manifests for external, HTTP, Python and
  declarative plugins.

## CLI

```bash
archub-sdk-release
archub-sdk-release --json
```

## Compatibility

SDK 1.0.0 targets ArcHub Platform `2.0.0` capability surfaces and the
`archub-platform-sdk` Python package. The client keeps transport injectable so
tests, API gateways and non-HTTP bridges can provide a custom transport without
monkeypatching network calls.
