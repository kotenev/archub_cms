# Architecture

ArcHub CMS is organized around a clean product boundary.

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| Storage and content model | `archub_cms.services.cms` | Content types, tree, versions, workflow, delivery payloads |
| Content Builder | `archub_cms.services.content_builder` | Block registry, normalization, audit and rendering |
| Runtime exports | `archub_cms.services.runtime` | Export published bot/RAG material snapshots |
| Web routes | `archub_cms.web.routes` | Backoffice, public delivery and headless API |
| Integration ports | `archub_cms.ports` | Auth, templates, runtime sources, audit and cache invalidation |
| RAG registry | `archub_cms.integrations.rag` | Corpus specs and external indexer hook |

## Host integration

The standalone release ships with local defaults. Production hosts should replace
or wrap:

- `AuthPort` for editor identity;
- `TemplatePort` for host-specific layout integration;
- `RuntimeSourcePort` for domain-specific resources;
- `CacheInvalidationPort` for process caches;
- `AuditSink` for structured audit events.

## Persistence

The initial release uses SQLite for portability. The service layer keeps the
storage boundary centralized, so a future PostgreSQL adapter can be added without
changing public delivery routes.
