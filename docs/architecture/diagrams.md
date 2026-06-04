# Diagrams & Models

Architecture model sources live under `docs/diagrams/`. Mermaid diagrams are
embedded in MkDocs pages. PlantUML, Archi/ArchiMate, and Structurizr files are
kept as renderable source artifacts so contributors can regenerate images or
import the model into their preferred tool.

## Source Inventory

| Format | Files | Use |
|---|---|---|
| Mermaid | `docs/diagrams/mermaid/*.mmd` | Quick rendered diagrams in MkDocs and GitHub previews. |
| PlantUML | `docs/diagrams/plantuml/*.puml` | System context, container, publishing, delivery, media, package, helper, and maintenance diagrams. |
| Archi/ArchiMate | `docs/diagrams/archi/*` | ArchiMate layer view and CSV import model for Archi users. |
| Structurizr | `docs/diagrams/structurizr/workspace.dsl` | C4-style model for system context and container views. |

## Rendering Commands

```bash
# Mermaid CLI, if installed
mmdc -i docs/diagrams/mermaid/container.mmd -o site/container.svg

# PlantUML, if installed
plantuml -tsvg docs/diagrams/plantuml/*.puml

# Structurizr CLI, if installed
structurizr validate -workspace docs/diagrams/structurizr/workspace.dsl
```

## Mermaid Container View

```mermaid
flowchart TB
    subgraph Package[archub_cms package]
        App[create_archub_app]
        Routes[web.routes]
        CMS[services.cms]
        Builder[services.content_builder]
        Runtime[services.runtime]
        Ports[ports.py]
        RAG[integrations.rag]
    end

    Editor[Content editor] --> Routes
    Visitor[Public visitor] --> Routes
    Host[Host FastAPI app] --> Ports
    App --> Routes
    Routes --> CMS
    Routes --> Builder
    Routes --> Runtime
    Runtime --> RAG
    CMS --> DB[(SQLite)]
    CMS --> Files[Runtime export files]
```

## Structurizr Scope

The Structurizr workspace models ArcHub CMS as a software system with containers
for the router, CMS service, Content Builder, runtime helpers, RAG registry,
templates/static assets, SQLite store, and runtime snapshot files. It also shows
external actors: content editors, public visitors, host applications, and
downstream runtime/indexing processes.

## Archi/ArchiMate Scope

The ArchiMate model describes three layers:

- Business: content editor, public visitor, and runtime consumer roles.
- Application: admin service, delivery service, CMS service, Content Builder,
  runtime export service, and port contracts.
- Technology/data: FastAPI process, SQLite database, static assets, and runtime
  snapshot filesystem.

Use `docs/diagrams/archi/elements.csv` and
`docs/diagrams/archi/relationships.csv` as a compact Archi import starting
point, or render the ArchiMate PlantUML source directly.

## PlantUML Source Set

- `system-context.puml`: external actors and ArcHub CMS boundary.
- `container.puml`: package-level components and data stores.
- `publish-flow.puml`: editor publish command through validation, versioning,
  webhooks, and runtime export.
- `advanced-cms-layers.puml`: target clean architecture layers.
- `target-modularization.puml`: gradual breakup of the monolithic CMS service.
- `content-modeling-service.puml`: schema-driven modeling boundary for data
  types, templates, content types, compositions, and blueprints.
- `content-model-update-flow.puml`: content model update sequence and future
  event-handler hooks.
- `versioning-service.puml`: content history, rollback, and retention cleanup
  application boundary.
- `version-cleanup-flow.puml`: keep-latest and age-based pruning sequence.
- `enterprise-knowledge-platform.puml`: DDD knowledge-base boundary with plugin
  registry and LLM ports.
- `knowledge-answer-flow.puml`: retrieval, RAG source merge, and grounded answer
  sequence.
- `plugin-manifest-lifecycle.puml`: manifest validation and future runtime
  binding.
- `published-helper.puml`: `ArcHubContentHelper` and `PublishedContent` facade.
- `maintenance-jobs.puml`: scheduled publishing, webhook dispatch, runtime
  export, and health reporting.
- `delivery-application-service.puml`: current route-to-application-service
  delivery boundary.
- `delivery-projection-flow.puml`: `fields`, `expand`, culture/segment, and
  public access request flow.
- `publishing-application-service.puml`: lifecycle command boundary for
  publish, workflow, trash, and runtime side effects.
- `domain-events-flow.puml`: future event-handler direction for audit,
  webhooks, cache invalidation, indexing, and runtime export.
- `media-library-service.puml`: media policy and report application boundary.
- `media-usage-report.puml`: usage, duplicate, folder, and orphaned asset
  report generation.
- `package-promotion-service.puml`: package export/import application service
  boundary and event flow.
- `package-import-plan.puml`: package dry-run planning and import sequence.
- `webhook-application-service.puml`: webhook management and maintenance
  dispatch application boundary.
- `webhook-dispatch-flow.puml`: durable webhook delivery, retry, and failure
  state transitions.
- `governance-service.puml`: editor permissions, public access route guards,
  and governance domain events.
- `public-access-flow.puml`: member-gated public delivery decision flow.
