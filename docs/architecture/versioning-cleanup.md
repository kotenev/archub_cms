# Versioning & Cleanup

ArcHub content history now has a dedicated application boundary:
`archub_cms.application.versioning.ArcHubVersioningService`. It owns version
listing, single-version lookup, rollback, and retention cleanup while
`ArcHubCMSService` remains the SQLite compatibility implementation.

## Responsibilities

| Capability | Implementation |
|---|---|
| Version list | `versions(node_id)` returns newest-first snapshots for the editor UI. |
| Version JSON | `version(node_id, version_no)` exposes a single stored payload for diff tools. |
| Rollback | `restore(node_id, version_no)` restores a payload into the draft and emits `content.version.restored`. |
| Cleanup | `cleanup(node_id, keep_latest, older_than_seconds)` prunes historic snapshots and emits `content.versions.cleaned`. |
| Audit hook | Cleanup writes `content.versions.cleaned` activity when rows are removed. |

## Retention Policy

The current policy is intentionally conservative:

- keep at least the latest N versions per content node;
- optionally delete only versions older than a configured age;
- support a manual node-scoped admin endpoint:
  `POST /admin/archub/content/{node_id}/versions/cleanup`;
- expose the same command in the editor's **Versions** panel;
- keep the storage API independent from FastAPI forms and auth.

Example maintenance call:

```python
get_archub_versioning_service().cleanup(
    node_id="abc123",
    keep_latest=20,
    older_than_seconds=60 * 60 * 24 * 90,
    actor="maintenance",
)
```

For a forced manual prune, pass `older_than_seconds=None`; ArcHub will keep
only the latest N versions.

## Route Boundary

The following routes now call `ArcHubVersioningService`:

- `GET /admin/archub/content/{node_id}`
- `GET /admin/archub/content/{node_id}/versions/{version_no}/json`
- `POST /admin/archub/content/{node_id}/versions/{version_no}/restore`
- `POST /admin/archub/content/{node_id}/versions/cleanup`

The route layer still handles login, permission checks, form parsing, and
redirect/JSON responses. Version policy and rollback behavior stay in the
application service.

## Future Policy Extensions

Umbraco's cleanup model keeps recent history, retains selected daily versions,
supports document-type overrides, and allows important versions to be protected.
ArcHub should add those as schema-backed policies after the current application
boundary has enough production use:

- per-content-type retention overrides;
- "prevent cleanup" flags on selected versions;
- published-version protection;
- scheduled cleanup through `ArcHubMaintenanceService`;
- retention reports before destructive cleanup.

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/versioning-service.puml
plantuml -tsvg docs/diagrams/plantuml/version-cleanup-flow.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Content Version Cleanup](https://docs.umbraco.com/umbraco-cms/fundamentals/data/content-version-cleanup)
- [Umbraco Content Settings](https://docs.umbraco.com/umbraco-cms/reference/configuration/contentsettings)
- [Contentful Versions](https://www.contentful.com/help/content-and-entries/versions/)
- [Sanity History API](https://www.sanity.io/docs/http-reference/history)
