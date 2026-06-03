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
| Draft and publish | Existing + refactored | Nodes keep separate draft and published JSON payloads; commands run through `ArcHubPublishingService`. |
| Version history | Existing | Save/publish creates retrievable versions and restore actions. |
| Preview | Existing | Tokenized preview route and no-store preview headers. |
| Multilingual variants | Existing | Culture-specific published variants and delivery fallback. |
| Personalization | Existing | Segment-specific payload overrides and delivery fallback. |
| Domains and multi-site roots | Existing | Hostname-to-root/culture mapping through content domains. |
| Redirects | Existing | Source-to-target redirect rules with active flags. |
| Permissions and public access | Existing + refactored | `ArcHubGovernanceService` owns editor authorization, scoped actions, public access policies, and member gating. |
| Locks | Existing | Active edit locks with expiry and force release. |
| Workflow scheduling | Existing + refactored | `ArcHubPublishingService` applies due workflow transitions; `ArcHubMaintenanceService` invokes it operationally. |
| Webhooks | Existing + refactored | `ArcHubWebhookService` owns subscriptions, delivery logs, retry dispatch, signing, and maintenance integration. |
| Runtime/RAG export | Existing + refactored | Runtime snapshot freshness is checked and refreshed by maintenance. |
| Published content helper | Added | `ArcHubContentHelper` and `PublishedContent` provide Umbraco-style helper APIs. |
| Dictionary/localization helper | Added | Helper resolves dictionary values with culture fallback. |
| Media helper | Added | Helper resolves registered media by ID or URL. |
| Media/DAM reports | Added | `ArcHubMediaService` adds allowed-type policy, folder summaries, duplicate groups, usage reports, and orphaned asset detection. |
| Environments/promotions | Partial + refactored | `ArcHubPackageService` wraps export, inspection, dry-run plans, import, and promotion events; target architecture should add environment metadata and migration scripts. |
| Property expansion/limiting | Added | `fields`, `expand=properties[...]`, and `Start-Item` are handled by `application.delivery`. |
| Content version cleanup | Future | Add scheduled cleanup policy with per-content-type override. |
| Media cleanup/duplicate checks | Added | Duplicate/orphan reports are exposed as computed read models; destructive cleanup remains a future explicit command. |
| Realtime collaboration | Future | Track editor presence, optimistic concurrency, and conflict resolution. |
| GraphQL/OData delivery | Future | REST is present; optional query endpoint can be added after permission and expansion rules are formalized. |
| Audit/event bus | Partial + refactored | Activity exists; lifecycle commands now return `ArcHubDomainEvent` objects as the integration boundary. |

## Advanced CMS Pattern Mapping

| Pattern | Source inspiration | ArcHub implementation path |
|---|---|---|
| API-first delivery | Umbraco Delivery API, Contentful CDA/CPA, Strapi REST, Sanity Content Lake | Keep `/cms/api/*`, add expansion/limiting, preview contracts, and optional GraphQL later. |
| Schema-driven editing | Umbraco document types, Strapi Content-Type Builder, Sanity schemas | Continue content model APIs; extract validation and schema registry from `cms.py`. |
| Published-content read model | Umbraco `IPublishedContent` and helper APIs | Use `PublishedContent` and `ArcHubContentHelper` in templates and host integrations. |
| Operational background jobs | Umbraco scheduled publishing and cleanup jobs | Use `ArcHubMaintenanceService` as the host-neutral job boundary. |
| Composable integrations | Umbraco composers, modern headless webhooks/apps | Keep host ports and add explicit event handlers behind publishing/package/runtime actions. |
| Webhook delivery reliability | Umbraco, Strapi, Contentful, Sanity webhooks | Route subscription and dispatch operations through `ArcHubWebhookService`; keep durable delivery logs and retry state. |
| Governance and RBAC | Umbraco users/members, Contentful roles, Sanity roles, Strapi permissions | Route editor permissions and public access through `ArcHubGovernanceService`; keep host identity behind ports. |
| Environment promotion | Umbraco packages, Contentful environments, Strapi transfers, Sanity datasets | Route package operations through `ArcHubPackageService`; add environment metadata, signatures, and rollback plans later. |
| Fine-grained roles | Umbraco user groups, Sanity roles, Strapi RBAC | Keep permission rules; add reusable role templates and section-level policies. |

## Next Engineering Slices

1. Extend `application/delivery.py` with media-reference expansion and
   collection pagination metadata.
2. Extend publishing and package events with validation, signing, rollback, and
   runtime export intent metadata.
3. Replace remaining route-level side effects with event handlers for audit,
   runtime export, search indexing, and cache invalidation.
4. Add explicit media cleanup commands, thumbnail metadata, and external storage
   provider ports.
5. Add GraphQL/OData-style query adapters only after REST projection limits are
   covered by compatibility tests.

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Content Delivery API](https://docs.umbraco.com/umbraco-cms/reference/content-delivery-api)
- [Strapi REST API parameters](https://docs.strapi.io/cms/api/rest/parameters)
- [Contentful API overview](https://www.contentful.com/api/)
- [Contentful environments](https://www.contentful.com/help/environments/)
- [Contentful webhooks](https://www.contentful.com/developers/docs/webhooks/overview/)
- [Umbraco Webhooks](https://docs.umbraco.com/umbraco-cms/reference/webhooks)
- [Strapi Webhooks](https://docs.strapi.io/cms/backend-customization/webhooks)
- [Sanity webhooks](https://www.sanity.io/docs/content-lake/webhooks)
- [Contentful media](https://www.contentful.com/help/media/)
- [Contentful roles](https://www.contentful.com/help/roles/)
- [Contentful content permissions](https://www.contentful.com/help/content-permissions/)
- [Umbraco Packages](https://docs.umbraco.com/umbraco-cms/extending/packages)
- [Umbraco Security](https://docs.umbraco.com/umbraco-cms/reference/security)
- [Umbraco Members](https://docs.umbraco.com/umbraco-cms/fundamentals/data/members/)
- [Umbraco Media Management](https://docs.umbraco.com/umbraco-cms/tutorials/editors-manual/media-management)
- [Strapi Media Library](https://docs.strapi.io/cms/features/media-library)
- [Strapi Data Management](https://docs.strapi.io/cms/features/data-management)
- [Sanity assets](https://www.sanity.io/docs/content-lake/assets)
- [Sanity datasets](https://www.sanity.io/docs/content-lake/datasets)
- [Sanity roles](https://www.sanity.io/docs/user-guides/roles)
- [Sanity schemas and forms](https://www.sanity.io/docs/schemas-and-forms)
