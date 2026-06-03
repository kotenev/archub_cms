# Content Modeling

ArcHub content modeling now has a dedicated application boundary:
`archub_cms.application.modeling.ArcHubModelingService`. It owns schema-driven
editing use cases while the existing SQLite-backed CMS service remains the
compatibility implementation.

## Responsibilities

| Capability | Implementation |
|---|---|
| Data types | `upsert_data_type()` stores reusable editor configuration and validation. |
| Templates | `upsert_template()` validates local template views and content-type allowlists. |
| Compositions | `upsert_composition()` manages reusable field groups. |
| Content types | `upsert_content_type()` manages document/element schemas, allowed children, and template binding. |
| Blueprints | `upsert_blueprint()` and `delete_blueprint()` manage reusable starter payloads. |
| Reports | `report()` exposes the full model inventory for admin UI, packages, and docs. |

## Model Vocabulary

ArcHub intentionally mirrors familiar CMS concepts:

- **Data type:** reusable editor plus validation configuration.
- **Composition:** reusable group of fields shared by content types.
- **Content type:** document or element schema with fields, hierarchy rules,
  root permissions, icon, and template.
- **Blueprint:** reusable starter content payload for a content type.
- **Template:** local rendering view used by public HTML delivery.

The route layer parses HTTP forms and JSON. `ArcHubModelingService` owns the
use-case boundary and emits events such as `content_model.type.upserted` and
`content_model.blueprint.upserted`.

## Admin API Boundary

The following routes now call `ArcHubModelingService`:

- `GET /admin/archub/content-model.json`
- `GET|POST /admin/archub/content-model/data-types`
- `GET|POST /admin/archub/content-model/templates`
- `POST /admin/archub/content-model/compositions`
- `POST /admin/archub/content-model/types`
- `GET|POST /admin/archub/content-blueprints`
- `POST /admin/archub/content/{node_id}/blueprints`

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/content-modeling-service.puml
plantuml -tsvg docs/diagrams/plantuml/content-model-update-flow.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Defining Content](https://docs.umbraco.com/umbraco-cms/fundamentals/data/defining-content)
- [Strapi Content-Type Builder](https://docs.strapi.io/cms/features/content-type-builder)
- [Contentful content models](https://www.contentful.com/help/content-models/)
- [Sanity schemas and forms](https://www.sanity.io/docs/studio/schemas-and-forms)
