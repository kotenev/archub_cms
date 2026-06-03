# Package Promotion

ArcHub package import/export now has an application boundary:
`archub_cms.application.packages.ArcHubPackageService`. The service keeps the
existing admin endpoints stable while giving environment promotion a place for
validation, dry-run plans, events, and future migration policies.

## Responsibilities

| Capability | Implementation |
|---|---|
| Export | Wraps `export_content_package()` and emits `package.exported`. |
| Inspect | Validates schema, counts package sections, and emits `package.inspected`. |
| Dry-run plan | Wraps `plan_content_package_import()` and emits `package.import.planned`. |
| Import | Wraps `import_content_package()` and emits `package.imported` or `package.import.rejected`. |
| Compatibility | Routes return the same payload shape as before; events stay available to service callers. |

## Admin API Boundary

The following routes now call `ArcHubPackageService` instead of using the CMS
store directly:

- `GET /admin/archub/packages/export.json`
- `POST /admin/archub/packages/inspect`
- `POST /admin/archub/packages/plan`
- `POST /admin/archub/packages/import`

This follows the same extraction pattern as publishing, delivery, and media:
route handlers parse HTTP input, application services own use-case semantics,
and the current SQLite-backed CMS service remains the compatibility
implementation.

## Promotion Rules

Imports should be planned before execution. A plan can report create, update,
skip, and conflict actions before destructive changes are made. Future work
should add environment IDs, package signatures, schema migration steps, and
explicit rollback metadata before packages are promoted between shared
environments.

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/package-promotion-service.puml
plantuml -tsvg docs/diagrams/plantuml/package-import-plan.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Packages](https://docs.umbraco.com/umbraco-cms/extending/packages)
- [Contentful environments](https://www.contentful.com/help/environments/)
- [Strapi Data Management](https://docs.strapi.io/cms/features/data-management)
- [Sanity datasets](https://www.sanity.io/docs/content-lake/datasets)
