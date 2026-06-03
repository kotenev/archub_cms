# Advanced CMS Refactor

This refactor aligns ArcHub CMS with proven ideas from Umbraco and modern
headless CMS platforms while preserving the package's FastAPI-first public API.
The implemented refactoring introduces stable architectural seams:
`ArcHubDeliveryService`, `ArcHubPublishingService`, `ArcHubDomainEvent`,
`ArcHubMediaService`, `ArcHubPackageService`, `ArcHubWebhookService`,
`ArcHubGovernanceService`, `ArcHubContentHelper`, `PublishedContent`, and
`ArcHubMaintenanceService`.

## Design Inputs

The local `books/umbraco_cms.pdf` chapters on Umbraco emphasize a CMS composed
from backoffice, website rendering, delivery API, extension composers, database
bootstrapping, background jobs, document types, culture variants, media,
permissions, content version cleanup, helpers for published content, and
template rendering. Current official Umbraco Delivery API documentation also
highlights published-content JSON, route/start-item context, culture handling,
protected content, and property expansion/limiting. Strapi, Contentful, and
Sanity reinforce common headless patterns: content models, draft/publish,
preview, i18n, roles, webhooks, environments/datasets, API-first delivery, and
structured schema-driven editing.

## Refactoring Principles

- Keep existing routes and service methods stable until callers are migrated.
- Move developer-facing reads through published-content facades instead of raw
  dictionaries.
- Treat long-running CMS behavior as operational jobs, not request-only logic.
- Keep domain-specific runtime/RAG behavior behind ports and integration hooks.
- Prefer thin application services over direct route-to-storage coupling.
- Add documentation and diagrams with every architectural seam.

## Target Layers

```text
web/                  FastAPI route adapters and templates
application/          use cases: publish, preview, package import, export
domain/               content, media, workflow, permissions, events
infrastructure/       SQLite repositories, files, webhook transport
published.py          helper facade for delivery/template consumers
services/jobs.py      maintenance orchestration for scheduled CMS work
ports.py              host-provided auth, templates, runtime, audit, cache
```

Today, `services/cms.py` still owns much of application, domain, and
infrastructure behavior. New code should depend on the facades first, then
incrementally extract cohesive modules behind the existing API.

## Implemented Architectural Seams

### Published Content Facade

`PublishedContent` wraps a published node, localized payload, route metadata,
tree traversal, and typed value access. `ArcHubContentHelper` adds Umbraco-style
helper operations:

- `content("/cms/demo")` or `content(node_id)`
- `query(content_type_alias="page", tag="docs")`
- `dictionary_value("WelcomeText", culture="fr-FR")`
- `media(asset_id)` and `media_by_url(url)`
- `render_content_blocks(content)`

This gives templates and host integrations a stable published-content API while
the storage internals evolve.

### Delivery Application Service

`ArcHubDeliveryService` is the first application-layer extraction from the
large CMS service. It owns delivery query contracts instead of leaving every
route to assemble payloads directly:

- `fields=title,summary` limits returned content properties;
- `expand=properties[summary]` expands path-like content references;
- `expand=properties[$all]` tries expansion for all path-like properties;
- `Start-Item: /cms/demo` or `start_item=/cms/demo` scopes tree delivery to a
  published root;
- culture and segment fallback remain delegated to the CMS read model.

The route URLs stay stable while implementation moves behind the application
service.

### Publishing Application Service

`ArcHubPublishingService` owns content lifecycle commands that used to be
triggered directly from route handlers:

- publish and unpublish;
- update workflow schedule/assignment;
- apply due workflow transitions;
- delete, restore from trash, and purge;
- refresh derived runtime exports as a command side effect;
- return explicit `ArcHubDomainEvent` instances for integration adapters.

This is the current boundary for future event handlers: audit, webhooks, cache
invalidation, runtime exports, search indexing, and external host integrations.

### Media/DAM Application Service

`ArcHubMediaService` owns media-library policy and reports:

- allowed content type policy via `ARCHUB_ALLOWED_MEDIA_CONTENT_TYPES`;
- required alt text for image references;
- folder summary reports;
- duplicate detection by metadata hash or original filename/content type;
- usage reports by scanning draft and published content payloads;
- orphaned asset detection for cleanup workflows.

This follows Umbraco media-library guidance and common DAM patterns from
Strapi, Contentful, and Sanity while keeping file storage provider concerns
outside the standalone package.

### Package Promotion Application Service

`ArcHubPackageService` owns package promotion use cases:

- export packages and emit `package.exported`;
- inspect package schema and section counts;
- create dry-run import plans and emit `package.import.planned`;
- import or reject packages with explicit result events;
- keep admin route payloads compatible while service callers can consume
  domain events.

This aligns ArcHub with Umbraco package concepts and environment-promotion
patterns from Contentful, Strapi, and Sanity.

### Webhook Integration Application Service

`ArcHubWebhookService` owns webhook integration operations:

- list and upsert subscriptions;
- expose durable delivery attempts;
- dispatch due `pending` and `retry` deliveries;
- keep HMAC signing and ArcHub headers behind the compatibility API;
- emit `webhook.subscription.upserted` and `webhook.dispatch.completed`.

`ArcHubMaintenanceService` now dispatches through this boundary, matching
Umbraco, Strapi, Contentful, and Sanity webhook reliability patterns.

### Governance Application Service

`ArcHubGovernanceService` owns editor permissions and public access decisions:

- route guards use `can_user_perform()`;
- permission routes use grant/revoke/report use cases;
- public delivery uses `can_access_public_content()`;
- member-gated access stays small and host-auth compatible;
- permission and access updates emit governance domain events.

This follows Umbraco user/member separation and modern CMS role concepts from
Contentful, Sanity, and Strapi without embedding a full identity provider.

### Maintenance Service

`ArcHubMaintenanceService.run_once()` centralizes operational work:

- apply due scheduled publish/unpublish workflow rows;
- refresh runtime exports when published runtime content is newer than the
  manifest;
- dispatch pending webhook deliveries;
- return content health counters.

Hosts can run it from cron, a worker process, or the optional in-process
FastAPI lifespan worker controlled by `ARCHUB_BACKGROUND_JOBS=1`.

## Target Modularization

The large CMS service should be split only behind compatibility tests:

| Module seam | Extract from current service | Responsibility |
|---|---|---|
| `domain/content.py` | dataclasses and validation helpers | Content node/type/value objects and invariants. |
| `application/publishing.py` | publish/unpublish/workflow methods | Publish use cases, domain events, cache/runtime side effects. |
| `application/delivery.py` | published payload/search/tree/feed methods | Read model assembly and API projections. |
| `infrastructure/sqlite_store.py` | `_connect`, `_ensure_db`, row hydration | Persistence and migrations. |
| `application/media.py` | media registration/listing | Asset metadata and usage reports. |
| `application/packages.py` | package export/import methods | Environment promotion and migrations. |
| `application/webhooks.py` | webhook queue and dispatch | Event subscription and retry policy. |
| `application/governance.py` | permission and access methods | Editor authorization, public access, member gating. |

## PlantUML

Primary source files:

- `docs/diagrams/plantuml/advanced-cms-layers.puml`
- `docs/diagrams/plantuml/target-modularization.puml`
- `docs/diagrams/plantuml/published-helper.puml`
- `docs/diagrams/plantuml/maintenance-jobs.puml`
- `docs/diagrams/plantuml/delivery-application-service.puml`
- `docs/diagrams/plantuml/delivery-projection-flow.puml`
- `docs/diagrams/plantuml/publishing-application-service.puml`
- `docs/diagrams/plantuml/domain-events-flow.puml`
- `docs/diagrams/plantuml/media-library-service.puml`
- `docs/diagrams/plantuml/media-usage-report.puml`
- `docs/diagrams/plantuml/package-promotion-service.puml`
- `docs/diagrams/plantuml/package-import-plan.puml`
- `docs/diagrams/plantuml/webhook-application-service.puml`
- `docs/diagrams/plantuml/webhook-dispatch-flow.puml`
- `docs/diagrams/plantuml/governance-service.puml`
- `docs/diagrams/plantuml/public-access-flow.puml`

Render them with:

```bash
plantuml -tsvg docs/diagrams/plantuml/*.puml
```

## Environment Settings

| Variable | Purpose |
|---|---|
| `ARCHUB_BACKGROUND_JOBS` | Enables the optional in-process maintenance worker when set to `1`, `true`, `yes`, or `on`. |
| `ARCHUB_BACKGROUND_JOB_INTERVAL` | Maintenance interval in seconds. Default: `60`. |
| `ARCHUB_WEBHOOK_DISPATCH_LIMIT` | Maximum webhook deliveries per maintenance pass. Default: `50`. |

## Refactor Completion Criteria

- Routes depend on application services or helpers, not storage details.
- Publishing commands emit explicit domain events and return runtime export
  side-effect reports.
- Delivery API uses `ArcHubDeliveryService` for controlled property
  expansion/limiting and start-item context for multi-site trees.
- Media has usage reports, duplicate detection, allowed type policy, and access
  checks through `ArcHubMediaService`.
- Package import/export runs through `ArcHubPackageService` with inspection,
  dry-run planning, and promotion events.
- Webhook management and dispatch run through `ArcHubWebhookService` with
  subscription events and dispatch result events.
- Editor permissions and public access decisions run through
  `ArcHubGovernanceService`.
- Architecture diagrams are updated with each extracted module.

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Content Delivery API](https://docs.umbraco.com/umbraco-cms/reference/content-delivery-api)
- [Strapi REST API parameters](https://docs.strapi.io/cms/api/rest/parameters)
- [Contentful environments](https://www.contentful.com/help/environments/)
- [Contentful webhooks](https://www.contentful.com/developers/docs/concepts/webhooks/)
- [Umbraco Webhooks](https://docs.umbraco.com/umbraco-cms/reference/webhooks)
- [Strapi Webhooks](https://docs.strapi.io/cms/backend-customization/webhooks)
- [Sanity webhooks](https://www.sanity.io/docs/content-lake/webhooks)
- [Contentful media](https://www.contentful.com/help/media/)
- [Umbraco Packages](https://docs.umbraco.com/umbraco-cms/extending/packages)
- [Umbraco Media Management](https://docs.umbraco.com/umbraco-cms/tutorials/editors-manual/media-management)
- [Strapi Media Library](https://docs.strapi.io/cms/features/media-library)
- [Strapi Data Management](https://docs.strapi.io/cms/features/data-management)
- [Sanity assets](https://www.sanity.io/docs/content-lake/assets)
- [Sanity datasets](https://www.sanity.io/docs/content-lake/datasets)
- [Sanity roles](https://www.sanity.io/docs/user-guides/roles)
- [Contentful roles](https://www.contentful.com/help/roles/)
- [Contentful content permissions](https://www.contentful.com/help/content-permissions/)
- [Sanity schemas](https://www.sanity.io/docs/schemas-and-forms)
