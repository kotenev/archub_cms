# Plugins & Extensibility

ArcHub has a real plugin **runtime** (not just a manifest registry): it discovers,
permission-checks, loads and wires plugins, then fans domain events and host calls out
to their extensions. This is the seam the ITSM suite, the offline BPMN editor and the
example plugins all use.

Start with the [Plugin Catalog](../plugins/index.md) for bundled modules and
[Plugin Release Distributions](../plugins/release-distributions.md) for packaging.
See the [plugin system diagrams](../architecture/plugin-platform-adapter.md) and the
[Platform SDK](../sdk/platform-sdk.md) for automation.

## Two runtimes, chosen per plugin

A plugin is declared by a JSON **manifest** (`plugins/<name>/plugin.json`) and selected
by its `runtime`:

- `python` — trusted **in-process** plugin loaded by importlib from a
  `module:attribute` entrypoint.
- `http` / `external` — **sandboxed** plugin reached over HTTP (Forge-style isolation).
- `host` / `manifest` — declarative capability advert (not executed).

```json
{
  "id": "archub.itsm.service_desk",
  "name": "ITSM Service Desk",
  "version": "1.0.0",
  "capability": "workflow",
  "runtime": "python",
  "entrypoint": "archub_cms.extensibility.example_plugins.itsm.plugin:ITSMServiceDeskPlugin",
  "permissions": ["workflow:read", "workflow:write", "requests:read", "requests:write"],
  "enabled_by_default": true
}
```

The host enforces manifest `permissions` at the load boundary, persists per-plugin
enable/disable + settings, and isolates setup failures so one bad plugin can't break
the process.

## Extension points (SPI)

A plugin's `setup(context)` registers one or more **extensions**, each implementing a
protocol from the SPI. 25+ extension points cover the breadth of Wiki.js / Confluence
catalogs:

`EventHook` · `Search` · `SearchIndexer` · `LLMTool` · `Renderer` · `Macro` ·
`Importer` / `ImportFormat` · `Exporter` / `ExportFormat` · `Auth` · `Storage` ·
`Notification` · `Theme` · `ScheduledJob` · `AnalyticsProvider` · `WorkflowAction` ·
`ContentTransformer` · `SecurityPolicy` · `Editor` · `Connector` · `ChatHandler` ·
`DashboardWidget` · `LiveEdit` · `PageAction`.

```python
from archub_cms.extensibility.extension_points import MacroExt

class BadgeMacro(MacroExt):
    macro_name = "badge"
    def expand(self, arguments: dict) -> str:
        return f'<span class="archub-badge-{arguments.get("color","blue")}">{arguments.get("label","")}</span>'

class MyPlugin:
    plugin_id = "example.badges"
    def setup(self, context):
        context.register(BadgeMacro())
```

Inspect the loaded runtime:

```bash
curl http://127.0.0.1:8088/api/platform/plugins        # loaded plugins + classified extensions
curl http://127.0.0.1:8088/api/platform/extensions     # macros, renderers, tools, …
curl http://127.0.0.1:8088/api/platform/plugins/catalog
```

## The platform persistence adapter

Plugins never open a database directly. They ask the **`PluginPlatformAdapter`** —
handed to `setup()` on the context — for an **audited** repository:

- `service_desk_repository(settings)` — the ITSM request store (SQLite/Postgres).
- `document_repository(collection, settings)` — keyed JSON collections (catalog, SLA,
  CMDB, schemes) on the same backend.
- `sqlite_store(...)` / `postgres_store(...)` — lower-level audited stores.

Every store operation writes an immutable plugin audit entry, and the DSN is redacted
in audit metadata. This is the capability boundary that keeps plugins decoupled from
the host's storage while still being first-class. See
[Plugin Platform Adapter](../architecture/plugin-platform-adapter.md).

## Offline BPMN editor plugin

The visual workflow editor at `/admin/itsm/workflow` is itself a plugin —
`archub.bpmn.editor` — that registers an `EditorExt` (`editor_id="bpmn-offline"`) and
ships its own static assets:

- A **dependency-free** vanilla-JS SVG editor (`bpmn_editor.js` / `.css`) — **no CDN,
  no build step, no network**.
- The host serves the assets from the plugin package
  (`/admin/itsm/workflow/assets/{name}`), guarded against path traversal.
- The page is **offline-first**: it uses the plugin editor when loaded, and falls back
  to bpmn-js (CDN) only if the plugin is disabled.

```bash
curl http://127.0.0.1:8088/api/platform/plugins | python -c 'import sys,json; print("bpmn-offline" in json.load(sys.stdin)["editors"])'
# → True
```

This is the recommended pattern for shipping a UI capability as a plugin: an
`EditorExt` for discovery + bundled assets served by the host.

## Bundled example plugins

The repo ships runnable examples under
`src/archub_cms/extensibility/example_plugins/` with manifests in `plugins/`:
backlinks, content macros, markdown importer, Obsidian vault exporter, summarize tool,
header auth, storage backends, console notifications — plus the ITSM and offline-editor
plugins. They are the executable documentation for the SPI.

## Writing your own

1. Create a package with a plugin class exposing `setup(context)`.
2. Register extensions implementing SPI protocols.
3. Drop a `plugins/<name>/plugin.json` manifest (or point `ARCHUB_PLUGIN_DIRS` at your
   directory).
4. Restart — the host discovers, permission-checks and loads it; events and host calls
   start flowing to your extensions.

## Releasing a plugin

```bash
archub-marketplace-build --output dist/archub-marketplace --plugin-dir plugins
```

Then install from `/api/platform/plugins/install/file` or
`/api/platform/modules/marketplace/install`. External plugins should ship a Dockerfile,
`openapi.yaml`, `/health`, and `POST /api/arc-tool`.
