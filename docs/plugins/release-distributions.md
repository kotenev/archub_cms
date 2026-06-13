---
tags:
  - Plugins
  - Deployment
---

# Plugin and Module Release Distributions

ArcHub packages plugins, adapters, REST API modules and Rust core modules as
marketplace-ready ZIP archives. A marketplace repository is just a directory with a
`marketplace.json` index and versioned packages.

## Build a Marketplace Repository

```bash
python -m pip install -e ".[server]"
archub-marketplace-build --output dist/archub-marketplace --json
```

Options:

| Option | Use |
|---|---|
| `--plugin-dir plugins` | add a plugin source directory |
| `--no-builtins` | package only filesystem plugins |
| `--no-plugins` | package only built-in/core modules |
| `--no-replace` | fail if an archive already exists |

The builder skips runtime dependency directories such as `vendor`, `.venv`,
`node_modules`, `target` and caches so archives stay deterministic.

## Repository Layout

```text
dist/archub-marketplace/
  marketplace.json
  knowledge/archub.ru.wiki.php/1.0.0/archub.ru.wiki.php-1.0.0.zip
  knowledge/archub.olo.php/1.0.0/archub.olo.php-1.0.0.zip
  adapter/archub.adapter.sqlite/0.1.0/archub.adapter.sqlite-0.1.0.zip
```

Each index item includes:

- module id, name, version and capability;
- runtime, language, core flag and Rust crate when relevant;
- permissions, tags and provided contracts;
- archive path and `sha256`.

## Install From a File

```bash
curl -X POST http://127.0.0.1:8088/api/platform/plugins/install/file \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "/srv/releases/archub.olo.php-1.0.0.zip",
    "replace": true,
    "enable": false
  }'
```

Supported sources: directory, `plugin.json`, `.zip`, `.tar`, `.tar.gz`.

## Install From a Marketplace

```bash
curl 'http://127.0.0.1:8088/api/platform/modules/marketplace?repository=/srv/releases/archub-marketplace'

curl -X POST http://127.0.0.1:8088/api/platform/modules/marketplace/install \
  -H 'Content-Type: application/json' \
  -d '{
    "repository": "/srv/releases/archub-marketplace",
    "module_id": "archub.ru.wiki.php",
    "version": "1.0.0",
    "enable": false
  }'
```

The installer verifies `sha256` when the marketplace item declares it and writes the
module into the first configured `ARCHUB_PLUGIN_DIRS` directory.

## External PHP Plugins

PHP plugins are distributed as ArcHub modules and deployed as separate services:

```bash
cd plugins/archub_ru_wiki_php
composer install --no-dev --optimize-autoloader
php -S 0.0.0.0:8097 -t public

cd ../archub_olo_php
composer install --no-dev --optimize-autoloader
php -S 0.0.0.0:8098 -t public
```

In Docker:

```bash
docker build -t archub-ru-wiki-php plugins/archub_ru_wiki_php
docker run --rm -p 8097:8097 archub-ru-wiki-php
```

Enable the manifest after the service responds to `/health`.

## Release Gate

- `plugin.json` validates and declares minimal permissions.
- External services expose `/health` and `POST /api/arc-tool`.
- `openapi.yaml` matches the runtime endpoint contract.
- Archives are reproducible and exclude local dependency folders.
- Marketplace `sha256` values are checked during promotion.
- Plugin storage uses the platform adapter and audit sink.
