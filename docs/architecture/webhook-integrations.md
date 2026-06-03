# Webhook Integrations

ArcHub webhook management now has a dedicated application boundary:
`archub_cms.application.webhooks.ArcHubWebhookService`. The service keeps the
existing admin routes stable while concentrating subscription management,
delivery listing, retry dispatch, signing headers, and future integration
events in one use-case layer.

## Responsibilities

| Capability | Implementation |
|---|---|
| Subscriptions | `subscriptions()` lists active or inactive webhook definitions. |
| Upsert | `upsert()` validates target URL, event filters, retry policy, and emits `webhook.subscription.upserted`. |
| Deliveries | `deliveries()` exposes delivery attempts with status, attempts, payload, and errors. |
| Dispatch | `dispatch_pending()` sends due `pending`/`retry` deliveries and emits `webhook.dispatch.completed`. |
| Operations | `ArcHubMaintenanceService.run_once()` dispatches through this application boundary. |

## Admin API Boundary

The following routes now call `ArcHubWebhookService` instead of the CMS store
directly:

- `GET /admin/archub/webhooks.json`
- `POST /admin/archub/webhooks`
- `GET /admin/archub/webhooks/deliveries.json`
- `POST /admin/archub/webhooks/dispatch`

Webhook payloads are still queued by content lifecycle operations. Dispatch
adds ArcHub headers such as `X-ArcHub-Delivery`, `X-ArcHub-Event`, and optional
`X-ArcHub-Signature` for HMAC verification by receivers.

## Reliability Model

Deliveries remain durable in SQLite until processed. Failed attempts move to
`retry` with exponential backoff, then to `failed` after the subscription's
`max_attempts`. Hosts can run dispatch manually from the admin endpoint or
through the maintenance worker controlled by `ARCHUB_BACKGROUND_JOBS`.

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/webhook-application-service.puml
plantuml -tsvg docs/diagrams/plantuml/webhook-dispatch-flow.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Webhooks](https://docs.umbraco.com/umbraco-cms/reference/webhooks)
- [Strapi Webhooks](https://docs.strapi.io/cms/backend-customization/webhooks)
- [Contentful webhooks](https://www.contentful.com/developers/docs/webhooks/overview/)
- [Sanity webhooks](https://www.sanity.io/docs/content-lake/webhooks)
