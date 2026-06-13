---
tags:
  - Plugins
  - Deployment
---

# ArcHub.ru PHP Wiki Plugin

`archub.ru.wiki.php` is an external PHP 8.4 plugin that demonstrates a
Confluence-style wiki for `ArcHub.ru`. It runs out-of-process and connects to ArcHub
through its manifest and HTTP bridge.

## Capabilities

- Spaces, page tree, labels, owners, statuses and page versions.
- Macros for status, table of contents, children and embedded diagrams.
- Diagrams.net / Draw.io-compatible `.drawio` export.
- Search, backlinks graph and audit-ready metadata.
- ArcHub bridge: `POST /api/arc-tool`.

## Local Run

```bash
cd plugins/archub_ru_wiki_php
composer install
composer serve
```

Open `http://127.0.0.1:8097`. The manifest is disabled by default; enable it only
after `/health` responds.

## Docker Run

```bash
docker build -t archub-ru-wiki-php plugins/archub_ru_wiki_php
docker run --rm -p 8097:8097 archub-ru-wiki-php
```

## Marketplace Packaging

```bash
archub-marketplace-build --output dist/archub-marketplace --plugin-dir plugins
```

The archive includes `plugin.json`, `composer.json`, `public/`, `src/`,
`openapi.yaml`, static wiki assets and Draw.io-compatible client code. Local
`vendor/` is ignored by the distribution builder; install Composer dependencies in
the target image or service.

## Integration Checklist

- `runtime` is `external` or `http`.
- `enabled_by_default` is `false`.
- service exposes `/health`.
- service exposes `POST /api/arc-tool`.
- ArcHub can reach the configured `entrypoint`.
