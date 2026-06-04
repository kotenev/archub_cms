# Enterprise Knowledge Platform

ArcHub now has a dedicated DDD bounded context for corporate knowledge-base
workflows: `archub_cms.application.knowledge.ArcHubKnowledgeBaseService`.
It composes existing CMS content, RAG materials, governance, plugins, and LLM
ports without moving storage concerns into the domain model.

## Bounded Context

| DDD concept | ArcHub model |
|---|---|
| Aggregate | `KnowledgeSpace` groups published documents by route-root. |
| Entity | `KnowledgeDocument` projects published CMS nodes into searchable KB pages. |
| Relation | `KnowledgeEdge` models wiki links, CMS links, backlinks, and missing targets. |
| Read model | `KnowledgeGraph` exposes edge counts, orphaned pages, and unresolved links. |
| Port | `LLMProviderPort` allows offline and online answer providers. |
| Plugin manifest | `KnowledgePluginManifest` declares safe extension capabilities. |

The service keeps the current CMS service as the persistence adapter. Routes
call the application boundary, not SQLite or content tree internals.

## Platform Features

- Space catalog inspired by Confluence spaces.
- Published document search with tags, text, and space filtering.
- Wiki-style graph extraction from `[[wiki links]]`, markdown links, and
  `/cms/...` paths.
- Obsidian-compatible Markdown vault export for offline knowledge work.
- Grounded answer generation with source attribution.
- Offline default LLM provider: `offline-extractive`.
- Online/local provider: OpenAI-compatible `/chat/completions`, usable with
  cloud services or local servers such as Ollama-compatible gateways.
- Manifest-driven plugin catalog with built-in capability categories.

## Admin API

- `GET /admin/archub/knowledge/platform.json`
- `GET /admin/archub/knowledge/documents.json?q=incident&space=engineering`
- `GET /admin/archub/knowledge/graph.json?space=engineering`
- `GET /admin/archub/knowledge/plugins.json`
- `GET /admin/archub/knowledge/vault-export.json`
- `POST /admin/archub/knowledge/ask`

## Plugin Manifest

Plugins are discovered from `ARCHUB_PLUGIN_DIRS` or `plugins/`. A plugin is a
JSON manifest named `plugin.json` or `*.archub-plugin.json`. ArcHub validates
the manifest but does not execute plugin code by default.

Supported capability categories include `auth`, `storage`, `renderer`,
`search`, `llm_provider`, `llm_tool`, `sync`, `importer`, `exporter`, `macro`,
`theme`, `automation`, `notification`, `analytics`, `governance`,
`compliance`, `editor`, `workflow`, and `connector`.

## LLM Configuration

```bash
ARCHUB_LLM_PROVIDER=offline-extractive
ARCHUB_LLM_PROVIDER=openai-compatible
ARCHUB_LLM_BASE_URL=http://localhost:11434/v1
ARCHUB_LLM_MODEL=llama3.1
ARCHUB_LLM_API_KEY=...
```

Use `offline-extractive` for deterministic no-network answers. Use
`openai-compatible` for hosted models or local OpenAI-compatible gateways.

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/enterprise-knowledge-platform.puml
plantuml -tsvg docs/diagrams/plantuml/knowledge-answer-flow.puml
plantuml -tsvg docs/diagrams/plantuml/plugin-manifest-lifecycle.puml
```

## References

- [Wiki.js Modules](https://docs.requarks.io/dev/modules)
- [Obsidian Vault API](https://docs.obsidian.md/Plugins/Vault)
- [Obsidian Manifest](https://docs.obsidian.md/Reference/Manifest)
- [Confluence Cloud REST API](https://developer.atlassian.com/cloud/confluence/rest/v1/intro/)
- [Atlassian Forge for Confluence](https://developer.atlassian.com/cloud/confluence/forge/)
