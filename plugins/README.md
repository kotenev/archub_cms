# ArcHub Plugin Manifests

ArcHub discovers plugin manifests from `ARCHUB_PLUGIN_DIRS` or the local
`plugins/` directory. A manifest must be named `plugin.json` or
`*.archub-plugin.json`.

The registry validates manifests and exposes capabilities. It does not execute
plugin code by default; hosts can bind trusted manifests to HTTP services,
sandbox workers, or Python entrypoints.

```json
{
  "id": "acme.macro.decision-log",
  "name": "Decision Log Macro",
  "version": "1.0.0",
  "capability": "macro",
  "runtime": "http",
  "entrypoint": "https://plugins.example.test/decision-log",
  "description": "Embeds ADR summaries in knowledge pages.",
  "permissions": ["content:read"],
  "tags": ["adr", "knowledge"]
}
```

Supported capabilities include `auth`, `storage`, `renderer`, `search`,
`llm_provider`, `llm_tool`, `sync`, `importer`, `exporter`, `macro`, `theme`,
`automation`, `notification`, `analytics`, `governance`, `compliance`,
`editor`, `workflow`, `connector`, `knowledge`, `media`, `collaboration`,
`cms`, `adapter`, `rest_api`, and `platform_module`.

External services such as `archub_ru_wiki_php` should use `runtime: "external"`
or `runtime: "http"` and keep `enabled_by_default: false` unless the service is
managed by the same deployment.
