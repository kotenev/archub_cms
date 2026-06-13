---
tags:
  - Architecture
  - Deployment
---

# Documentation System

ArcHub documentation is a Docs-as-Code wiki built with ProperDocs, MkDocs Material,
PyMdown, PlantUML, Mermaid, Structurizr sources and a plugin toolchain.
Documentation changes should be reviewed like code: small diffs, strict build, and
links that can be verified in CI.

## Local Authoring

```bash
python -m pip install -e ".[docs]"
properdocs serve --dev-addr 127.0.0.1:8001
properdocs build --strict --site-dir site
```

Use `properdocs serve` while editing. Run the strict build before a pull request.
`properdocs.yml` is canonical; `mkdocs.yml` inherits it for existing local habits.

## Enabled Wiki Plugins

| Plugin | Purpose |
|---|---|
| `search` | client-side search with English/Russian tokenization |
| `tags` | generated topic index at [Tags](../reference/tags.md) |
| `glightbox` | zoomable screenshots and diagrams |
| `git-revision-date-localized` | page update and creation dates from Git |
| `macros` | reusable variables/snippets for future release automation |
| `redirects` | stable old links after navigation refactors |
| `minify` | compact HTML/CSS/JS for published artifacts |
| `plantuml_markdown` | inline PlantUML and C4 rendering |

`properdocs` is installed directly through the docs toolchain and also used by
`mkdocs-redirects`. The theme uses system fonts (`font: false`) so strict local builds
do not need Google Fonts access.

## Information Architecture

The navigation is task-first:

1. **Overview** — what ArcHub is and why it exists.
2. **Run & Deploy** — source, release artifacts, Docker, Kubernetes and Pages.
3. **Product** — user-facing capabilities.
4. **Plugins & Marketplace** — module catalog, packaging and external plugins.
5. **Architecture** — C4, DDD, bounded contexts and diagrams.
6. **SDK & API** — automation contracts.
7. **Docs as Code** — documentation maintenance and tags.

Keep new pages in the section where a reader would look for the task, not where the
source code happens to live.

## Diagrams

Preferred formats:

- PlantUML/C4 for architecture and deployment contracts.
- Mermaid for lightweight flows embedded in Markdown.
- Structurizr DSL for model export and tooling integration.
- ArchiMate CSV/PlantUML for enterprise architecture imports.

Offline rendering:

```bash
plantuml -tsvg docs/diagrams/plantuml/*.puml
plantuml -tsvg docs/diagrams/c4/*.puml
```

The default ProperDocs build renders PlantUML through the configured server. For sealed
environments, point `plantuml_markdown.server` at an internal PlantUML server or
pre-render SVG files.

## Page Standard

Every article should answer:

- what the reader can do after reading it;
- which command, API or file is authoritative;
- which deployment mode it applies to;
- where to go next.

Use admonitions for warnings and operational decisions, not for decoration. Prefer
short tables and copyable commands over narrative paragraphs.

## Release Checklist

```bash
ruff check src tests
python -m compileall -q src
pytest -q
properdocs build --strict --site-dir site
```

For documentation-only changes, `properdocs build --strict --site-dir site` is the
minimum gate.
