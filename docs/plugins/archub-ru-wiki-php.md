# ArcHub.ru PHP Wiki Plugin

`archub.ru.wiki.php` is an external ArcHub knowledge plugin that demonstrates a
Confluence-style wiki for `ArcHub.ru` on PHP 8.4 and Symfony 8 components.

## Capabilities

- Spaces, page tree, labels, owners, statuses and page versions.
- Macros for status, table of contents, children and embedded diagrams.
- Diagrams.net / Draw.io-compatible `.drawio` mxfile export.
- Search, backlinks graph, audit-ready metadata and template-style seeded pages.
- ArcHub external runtime endpoint: `POST /api/arc-tool`.

## Local Run

```bash
cd plugins/archub_ru_wiki_php
composer install
composer serve
```

Open `http://127.0.0.1:8097`. The ArcHub manifest keeps the plugin disabled by
default; enable it from plugin management only after the PHP service is running.

## Packaging

The normal marketplace generator packages the full plugin directory:

```bash
archub-marketplace-build --output dist/archub-marketplace
```

The archive includes `plugin.json`, `composer.json`, `public/`, `src/`,
`openapi.yaml`, static wiki assets and Draw.io-compatible client code.
