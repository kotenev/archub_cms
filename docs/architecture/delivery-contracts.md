# Delivery Contracts

ArcHub's headless delivery endpoints are served through
`ArcHubDeliveryService`, an application-layer facade over the existing CMS read
model. This keeps route handlers small and puts API-first projection rules in
one place.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /cms/api/content` | Root or query-selected published content item. |
| `GET /cms/api/content/{path}` | Published content item by route path. |
| `GET /cms/api/tree` | Published tree from the domain root or start item. |
| `GET /cms/api/search` | Published search results. |

## Shared Query Parameters

| Parameter | Applies to | Behavior |
|---|---|---|
| `culture` | content, tree, search | Selects a culture variant; falls back to invariant published payload when missing. |
| `segment` | content, tree, search | Selects a personalization segment; falls back to the resolved culture payload when missing. |
| `fields` | content, tree, search | Comma/space separated aliases to return, for example `fields=title,summary`. |
| `expand` | content, tree | Expands references. Use `properties[alias]`, `properties[a,b]`, `properties[$all]`, or `children`. |
| `include_children` | content | Keeps the previous default of returning children; can be disabled with `include_children=false`. |
| `start_item` | tree | Starts tree delivery from a published node ID or route path. |
| `Start-Item` header | tree | Header equivalent of `start_item`, useful for multi-site clients and edge gateways. |

## Examples

Limit the content payload:

```bash
curl "http://127.0.0.1:8088/cms/api/content/demo?fields=title,summary"
```

Expand a path-like property:

```bash
curl "http://127.0.0.1:8088/cms/api/content/related-content?expand=properties[summary]"
```

Scope tree delivery to a start item:

```bash
curl -H "Start-Item: /cms/demo" "http://127.0.0.1:8088/cms/api/tree"
```

Search with a minimal result projection:

```bash
curl "http://127.0.0.1:8088/cms/api/search?q=ArcHub&fields=title,route_path"
```

## Projection Semantics

`fields` limits content properties inside the `payload` object. Route metadata
such as `node_id`, `route_path`, `content_type_alias`, culture, segment, and
timestamps remain available so clients can still cache, link, and reconcile
responses.

`expand=properties[alias]` treats a string property beginning with `/cms` as a
published content reference and returns a shallow linked content object with its
projected payload. Expansion is depth-limited to avoid recursive graphs.

`expand=children` tells tree/content delivery that child nodes should be present
when the caller has disabled default children or is using a route that would
otherwise be shallow.

## Public Access

Route handlers still apply public access rules after the delivery service builds
payloads. Protected content returns `401` for anonymous users and `403` for
authenticated users without access. Preview-token delivery remains separate and
uses private no-store cache headers.

## PlantUML

Render the delivery diagrams with:

```bash
plantuml -tsvg docs/diagrams/plantuml/delivery-*.puml
```

Primary diagrams:

- `delivery-application-service.puml`
- `delivery-projection-flow.puml`

## References

- [Umbraco Content Delivery API](https://docs.umbraco.com/umbraco-cms/reference/content-delivery-api)
- [Strapi REST API parameters](https://docs.strapi.io/cms/api/rest/parameters)
- [Contentful API overview](https://www.contentful.com/api/)
- [Sanity Content Lake](https://www.sanity.io/docs/content-lake)
