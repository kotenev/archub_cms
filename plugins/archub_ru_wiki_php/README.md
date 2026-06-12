# ArcHub.ru Enterprise Wiki PHP Plugin

External ArcHub plugin demonstrating an enterprise wiki for `ArcHub.ru` on a
modern PHP stack: PHP 8.4 and Symfony 8 components.

## Capabilities

- Confluence-style spaces, page tree, labels, owners and page status.
- Page macros: table of contents, status badges, children, and diagrams.
- Diagrams.net / Draw.io-compatible diagram storage via `.drawio` mxfile XML.
- Knowledge graph, backlinks, search, audit feed and template catalog.
- HTTP integration endpoint for ArcHub external plugin runtime:
  `POST /api/arc-tool`.

## Run Locally

```bash
cd plugins/archub_ru_wiki_php
composer install
composer serve
```

Open `http://127.0.0.1:8097`.

Docker:

```bash
docker build -t archub-ru-wiki-php .
docker run --rm -p 8097:8097 --env-file .env.example archub-ru-wiki-php
```

## ArcHub Integration

The module is discovered through `plugin.json` and should stay disabled by
default in development. Start the PHP service, then enable
`archub.ru.wiki.php` from the ArcHub plugin management surface when testing the
external runtime bridge.
