---
tags:
  - CMS
  - SDK
---

# Delivery API

ArcHub separates draft editing from published delivery. Public endpoints serve the
published projection only; preview endpoints require generated tokens and return
private no-store headers.

## Public Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /cms` | published site root |
| `GET /cms/{path}` | published HTML page |
| `GET /cms/api/tree` | navigation tree |
| `GET /cms/api/content` | root content |
| `GET /cms/api/content/{path}` | content by route |
| `GET /cms/api/search?q=...` | published search |
| `GET /cms/api/tags` | tag index |
| `GET /cms/api/tags/{tag}` | tagged content |
| `GET /cms/feed.xml` | RSS feed |
| `GET /cms/sitemap.xml` | sitemap |
| `GET /cms/robots.txt` | crawler rules |

## Preview Endpoints

```http
POST /admin/archub/content/{node_id}/preview-tokens
GET /cms/api/preview/{token}
```

Preview responses use:

```http
Cache-Control: private, no-store
```

Published delivery uses deterministic `ETag`, `Last-Modified`, public max-age and
stale-while-revalidate settings.

## Query Contract

The delivery service supports:

- `fields` projection for JSON payloads;
- `expand` for nested properties;
- `Start-Item` header for subtree delivery;
- culture, segment and host-domain routing;
- public access checks and protected content handling.

See [Delivery Contracts](architecture/delivery-contracts.md) for the full contract.

## SDK Access

```python
from archub_platform_sdk import ArcHubClient

client = ArcHubClient("http://127.0.0.1:8088")
tree = client.delivery_tree(start_item="/")
page = client.delivery_content("welcome")
results = client.delivery_search("architecture")
```

## Frontend Integration

```http
GET /cms/api/tree
GET /cms/api/content/product/pricing
GET /cms/api/search?q=onboarding
```

Use server-side caching for public responses and revalidate on publish/webhook events.
For static site builds, consume the API during build and keep `/cms/sitemap.xml` as the
canonical SEO index.
