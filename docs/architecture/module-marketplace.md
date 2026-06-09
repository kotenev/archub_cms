# Module Distribution & Marketplace

ArcHub installable modules use the existing `plugin.json` contract for plugins,
adapters, REST APIs, renderers, tools, and other platform capabilities. The
physical install root is the first directory in `ARCHUB_PLUGIN_DIRS` (`plugins`
by default).

## Distribution Format

A module distribution can be:

- a directory containing exactly one `plugin.json` or `*.archub-plugin.json`;
- a single manifest file;
- a `.zip`, `.tar`, `.tar.gz`, or `.tgz` archive containing exactly one manifest.

Example manifest:

```json
{
  "id": "acme.rest.helpdesk",
  "name": "Helpdesk REST API",
  "version": "1.0.0",
  "capability": "rest_api",
  "runtime": "manifest",
  "description": "Adds a helpdesk API surface.",
  "enabled_by_default": false
}
```

Supported module capabilities include all plugin extension categories plus
`adapter`, `rest_api`, and `platform_module`.

## Marketplace Repository

A marketplace repository is a local checkout with `marketplace.json`,
`archub-marketplace.json`, or `.archub/marketplace.json`.

```json
{
  "modules": [
    {
      "id": "acme.adapter.crm",
      "name": "CRM Adapter",
      "version": "1.0.0",
      "capability": "adapter",
      "package": "packages/acme.adapter.crm.zip",
      "sha256": ""
    }
  ]
}
```

`package`, `archive`, `path`, or `manifest_path` may point to a distribution
inside the repository. `sha256` is optional but verified when present.

## REST API

- `GET /api/platform/modules/manage`
- `POST /api/platform/modules/install/file`
- `GET /api/platform/modules/marketplace?repository=/path/to/repo`
- `POST /api/platform/modules/marketplace/install`

The same operations are also exposed under `/api/platform/plugins/*` for
backward compatibility.

## Safety Rules

Archive extraction rejects path traversal and tar links. Existing installs are
not overwritten unless `replace: true` is supplied. Installation uses a staging
directory and then renames into the final module folder.
