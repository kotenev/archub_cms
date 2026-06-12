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
  "runtime": "rust",
  "core": true,
  "language": "rust",
  "rust_crate": "archub-rest-api",
  "description": "Adds a helpdesk API surface.",
  "enabled_by_default": false
}
```

Supported module capabilities include all plugin extension categories plus
`cms`, `adapter`, `rest_api`, and `platform_module`.

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

## Building a Local Marketplace

Use the generator to archive every discovered subsystem: built-in platform
modules, adapters, REST API modules, and filesystem plugins.

```bash
archub-marketplace-build --output dist/archub-marketplace
python -m archub_cms.tools.module_distributions --output dist/archub-marketplace --json
```

The generator writes a hierarchical catalog:

```text
dist/archub-marketplace/
  marketplace.json
  rest_api/archub.rest.platform/1.0.0/archub.rest.platform-1.0.0.zip
  adapter/archub.adapter.plugin-store/1.0.0/archub.adapter.plugin-store-1.0.0.zip
  workflow/archub.itsm.service_desk/1.0.0/archub.itsm.service_desk-1.0.0.zip
```

Options:

- `--plugin-dir plugins` adds a source directory; repeat for multiple roots.
- `--no-builtins` packages only filesystem plugins.
- `--no-plugins` packages only built-in platform subsystem manifests.
- `--no-replace` fails if a target archive already exists.

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
