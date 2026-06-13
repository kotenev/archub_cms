---
tags:
  - Deployment
---

# GitHub Pages Docs

The documentation site is built with MkDocs Material and deployed through GitHub
Actions Pages. The workflow publishes the MkDocs site plus the static `demo_site/`
folder; it does not run the FastAPI platform.

## Repository Setup

In GitHub:

1. Settings -> Pages -> Build and deployment -> Source: **GitHub Actions**.
2. Settings -> Actions -> General: allow Actions.
3. Ensure `site_url`, `repo_url` and `repo_name` in `properdocs.yml` match the repository.

## Local Validation

```bash
python -m pip install -e ".[docs]"
properdocs serve --dev-addr 127.0.0.1:8001
properdocs build --strict --site-dir site
```

The strict build fails on broken links, invalid nav entries or plugin errors.

## Workflow Summary

`.github/workflows/pages.yml` runs on `main` when documentation, `properdocs.yml`,
`mkdocs.yml`, `pyproject.toml`, `demo_site/` or the workflow changes.

```yaml
- uses: actions/checkout@v6.0.3
- uses: actions/setup-python@v6.2.0
- uses: actions/configure-pages@v6.0.0
- run: python -m pip install -e .[docs]
- run: properdocs build --strict --site-dir site
- run: mkdir -p site/demo && cp -R demo_site/. site/demo/
- uses: actions/upload-pages-artifact@v5.0.0
- uses: actions/deploy-pages@v5.0.0
```

## Documentation Plugins

The `docs` extra installs:

- MkDocs Material and PyMdown extensions;
- PlantUML Markdown;
- tags and search from Material;
- Git revision dates;
- GLightbox for diagrams/screenshots;
- macros;
- redirects with ProperDocs dependency;
- HTML/CSS/JS minification.

See [Documentation System](../handbook/docs-as-code.md).

## PlantUML in CI

PlantUML diagrams render through the server configured in `properdocs.yml`. GitHub-hosted
runners have outbound network, so the public server works. For reproducible offline
builds, point `plantuml_markdown.server` at an internal PlantUML service or pre-render
SVGs with:

```bash
plantuml -tsvg docs/diagrams/plantuml/*.puml
plantuml -tsvg docs/diagrams/c4/*.puml
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Pages URL returns 404 | confirm Pages source is **GitHub Actions** |
| CSS or sitemap uses the wrong base URL | update `site_url` |
| Action fails on docs plugins | run `python -m pip install -e ".[docs]"` locally |
| Broken link fails strict build | fix the link or add a redirect map |
| PlantUML missing | check server reachability or render offline |
