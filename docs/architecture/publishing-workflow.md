# Publishing & Workflow

ArcHub publishing now has an application-layer boundary:
`archub_cms.application.publishing.ArcHubPublishingService`. Admin routes keep
their existing URLs, but lifecycle commands no longer call storage methods and
runtime export side effects directly.

## Commands

| Method | Route usage | Result |
|---|---|---|
| `publish(node_id, actor=...)` | `POST /admin/archub/content/{node_id}/publish` | Publishes draft JSON, emits `content.published`, refreshes runtime export. |
| `unpublish(node_id, actor=...)` | `POST /admin/archub/content/{node_id}/unpublish` | Moves content out of published delivery, emits `content.unpublished`, refreshes runtime export. |
| `update_workflow(...)` | `POST /admin/archub/content/{node_id}/workflow` | Stores state, assignment, schedule, and emits `content.workflow.updated`. |
| `apply_due_workflows(actor=...)` | `POST /admin/archub/workflow/apply-due` and maintenance jobs | Applies due scheduled publish/unpublish transitions and emits events. |
| `delete(...)` | `POST /admin/archub/content/{node_id}/delete` | Moves content to trash, emits `content.deleted`, refreshes runtime export. |
| `restore_from_trash(...)` | `POST /admin/archub/content/{node_id}/restore-from-trash` | Restores a trashed node and emits `content.restored`. |
| `purge(...)` | `POST /admin/archub/content/{node_id}/purge` | Permanently removes trashed content and emits `content.purged`. |

## Result Contract

Every command returns `PublishingCommandResult`:

```python
result.action
result.node
result.workflow
result.report
result.events
result.runtime_export
result.runtime_export_error
```

Routes currently use the result for redirects and JSON reports. Future adapters
can persist or publish `result.events` without changing route handlers.

## Domain Events

Events use `ArcHubDomainEvent` from `archub_cms.domain.events`:

```python
ArcHubDomainEvent(
    event_type="content.published",
    aggregate_id=node_id,
    actor="editor",
    metadata={"route_path": "/cms/demo"},
)
```

The event list is the integration seam for audit, webhook, cache invalidation,
runtime export, search indexing, and external host adapters.

## Runtime Export Side Effect

Publishing commands refresh runtime snapshots after lifecycle operations. A
failed export is captured in `runtime_export_error` and logged; it does not
turn a successful content command into a failed editor action. This matches the
previous route behavior while moving responsibility into the application layer.

## PlantUML

Render the related diagrams with:

```bash
plantuml -tsvg docs/diagrams/plantuml/publishing-application-service.puml
plantuml -tsvg docs/diagrams/plantuml/domain-events-flow.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco scheduled publishing concepts](https://docs.umbraco.com/umbraco-cms/reference/scheduling)
- [Contentful webhooks](https://www.contentful.com/developers/docs/concepts/webhooks/)
- [Sanity releases](https://www.sanity.io/docs/releases)
