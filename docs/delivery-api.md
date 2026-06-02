# Delivery API

ArcHub separates draft editing from published delivery.

## Published HTML

- `GET /cms`
- `GET /cms/{path}`

## Headless JSON

- `GET /cms/api/tree`
- `GET /cms/api/content`
- `GET /cms/api/content/{path}`
- `GET /cms/api/search?q=...`
- `GET /cms/api/tags`
- `GET /cms/api/tags/{tag}`

## Feeds

- `GET /cms/feed.xml`
- `GET /cms/sitemap.xml`

## Preview

- `POST /admin/archub/content/{node_id}/preview-tokens`
- `GET /cms/api/preview/{token}`

Preview responses use `Cache-Control: private, no-store`; published delivery
uses deterministic `ETag` and `Last-Modified` headers.
