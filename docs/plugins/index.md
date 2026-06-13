---
tags:
  - Plugins
  - Deployment
---

# Plugin Catalog

ArcHub plugins are platform modules described by `plugin.json`. They may run
in-process (`python`), as external HTTP services (`http` / `external`), or as
declarative core modules (`manifest`, `host`, `rust`).

## Bundled Modules

| Plugin | Runtime | Capability | Purpose |
|---|---|---|---|
| `archub.cms.core` | Rust/core | `cms` | core CMS content, modeling, publishing and delivery contract |
| `archub.itsm.service_desk` | Python | `workflow` | ITIL Service Desk, SLA, catalog, CMDB and BPMN schemes |
| `archub.bpmn.editor` | Python/static | `editor` | offline BPMN workflow editor |
| `archub.ru.wiki.php` | external PHP | `knowledge` | Confluence-style wiki demo for ArcHub.ru |
| `archub.olo.php` | external PHP | `knowledge` | OurLifeOrganized-style task manager demo |
| `archub.markdown.importer` | Python | `importer` | Markdown import workflow |
| `archub.vault.exporter` | Python | `exporter` | Obsidian vault export |
| `archub.summarize_tool` | Python | `llm_tool` | grounded summarization tool |
| `archub.header_auth` | Python | `auth` | header-based auth adapter example |

Use the runtime catalog for the current environment:

```bash
curl http://127.0.0.1:8088/api/platform/plugins
curl http://127.0.0.1:8088/api/platform/extensions
curl http://127.0.0.1:8088/api/platform/plugins/catalog
```

## Manifest Contract

```json
{
  "id": "acme.decision.macro",
  "name": "Decision Macro",
  "version": "1.0.0",
  "capability": "macro",
  "runtime": "http",
  "entrypoint": "http://decision-macro:8090/api/arc-tool",
  "permissions": ["content:read"],
  "enabled_by_default": false,
  "tags": ["knowledge", "adr"]
}
```

Rules:

- Keep external plugins disabled by default unless the same deployment manages the
  service.
- Declare the minimum permission set; the host gates plugin setup and API calls.
- Persist data through the platform adapter only. Direct plugin DB access bypasses
  audit and is not allowed.
- Ship `openapi.yaml` for HTTP plugins and `README.md` for marketplace users.

## Runtime Lifecycle

1. Discovery reads every manifest under `ARCHUB_PLUGIN_DIRS`.
2. Validation checks ids, version, runtime, capability and permissions.
3. Enablement state is loaded from the platform plugin store.
4. Python plugins are imported; HTTP/external plugins are represented by their endpoint.
5. Extensions are classified into search, macro, editor, workflow, auth, connector and
   other SPI groups.
6. Plugin storage calls are audited through the platform adapter.

See [Plugins & Extensibility](../capabilities/plugins.md) for SPI details and
[Release Distributions](release-distributions.md) for packaging.
