# CMS Capability Matrix

This matrix maps ArcHub CMS to capabilities commonly found in Umbraco and
advanced headless CMS platforms. It distinguishes existing behavior, the
refactoring seam added in this change, and future extraction work.

| Capability | ArcHub status | Architecture note |
|---|---|---|
| Backoffice | Existing | `/admin/archub` provides editing, modeling, runtime, permissions, workflow, package, media, dictionary, webhook, and health screens. |
| Published delivery API | Existing + refactored | `/cms/api/*`, RSS, sitemap, robots, public HTML, ETag, private/public cache behavior, and `ArcHubDeliveryService` projection contracts. |
| Document types and fields | Existing | `ContentType`, `ContentField`, data types, templates, compositions, and blueprints. |
| Element/block content | Existing | `ArcHubContentBuilderService` models reusable block types and blueprints. |
| Draft and publish | Existing | Nodes keep separate draft and published JSON payloads. |
| Version history | Existing | Save/publish creates retrievable versions and restore actions. |
| Preview | Existing | Tokenized preview route and no-store preview headers. |
| Multilingual variants | Existing | Culture-specific published variants and delivery fallback. |
| Personalization | Existing | Segment-specific payload overrides and delivery fallback. |
| Domains and multi-site roots | Existing | Hostname-to-root/culture mapping through content domains. |
| Redirects | Existing | Source-to-target redirect rules with active flags. |
| Permissions and public access | Existing | Editor permission rules and public access policies. |
| Locks | Existing | Active edit locks with expiry and force release. |
| Workflow scheduling | Existing + refactored | `ArcHubMaintenanceService` now gives scheduled work a single operational entrypoint. |
| Webhooks | Existing + refactored | Queue, retry, signing, and dispatch are exposed through the maintenance service. |
| Runtime/RAG export | Existing + refactored | Runtime snapshot freshness is checked and refreshed by maintenance. |
| Published content helper | Added | `ArcHubContentHelper` and `PublishedContent` provide Umbraco-style helper APIs. |
| Dictionary/localization helper | Added | Helper resolves dictionary values with culture fallback. |
| Media helper | Added | Helper resolves registered media by ID or URL. |
| Environments/promotions | Partial | Package export/import exists; target architecture should add environment metadata and migration scripts. |
| Property expansion/limiting | Added | `fields`, `expand=properties[...]`, and `Start-Item` are handled by `application.delivery`. |
| Content version cleanup | Future | Add scheduled cleanup policy with per-content-type override. |
| Media cleanup/duplicate checks | Future | Add media usage graph, duplicate detector, allowed type policy, and orphan cleanup. |
| Realtime collaboration | Future | Track editor presence, optimistic concurrency, and conflict resolution. |
| GraphQL/OData delivery | Future | REST is present; optional query endpoint can be added after permission and expansion rules are formalized. |
| Audit/event bus | Partial | Activity exists; target architecture should promote explicit domain events. |

## Advanced CMS Pattern Mapping

| Pattern | Source inspiration | ArcHub implementation path |
|---|---|---|
| API-first delivery | Umbraco Delivery API, Contentful CDA/CPA, Strapi REST, Sanity Content Lake | Keep `/cms/api/*`, add expansion/limiting, preview contracts, and optional GraphQL later. |
| Schema-driven editing | Umbraco document types, Strapi Content-Type Builder, Sanity schemas | Continue content model APIs; extract validation and schema registry from `cms.py`. |
| Published-content read model | Umbraco `IPublishedContent` and helper APIs | Use `PublishedContent` and `ArcHubContentHelper` in templates and host integrations. |
| Operational background jobs | Umbraco scheduled publishing and cleanup jobs | Use `ArcHubMaintenanceService` as the host-neutral job boundary. |
| Composable integrations | Umbraco composers, modern headless webhooks/apps | Keep host ports and add explicit event handlers behind publishing/package/runtime actions. |
| Environment promotion | Contentful environments, package migration flows | Evolve package import/export into environment-aware migrations and dry-run plans. |
| Fine-grained roles | Umbraco user groups, Sanity roles, Strapi RBAC | Keep permission rules; add reusable role templates and section-level policies. |

## Next Engineering Slices

1. Extend `application/delivery.py` with media-reference expansion and
   collection pagination metadata.
2. Extract publishing commands and emit explicit events:
   `content.publishing.validated`, `content.published`, `runtime.export.requested`.
3. Replace route-level side effects with event handlers for audit, webhooks,
   runtime export, and cache invalidation.
4. Add media policy enforcement and usage reports.
5. Add GraphQL/OData-style query adapters only after REST projection limits are
   covered by compatibility tests.

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Content Delivery API](https://docs.umbraco.com/umbraco-cms/reference/content-delivery-api)
- [Strapi REST API parameters](https://docs.strapi.io/cms/api/rest/parameters)
- [Contentful API overview](https://www.contentful.com/api/)
- [Contentful environments](https://www.contentful.com/help/environments/)
- [Sanity roles](https://www.sanity.io/docs/user-guides/roles)
- [Sanity schemas and forms](https://www.sanity.io/docs/schemas-and-forms)
