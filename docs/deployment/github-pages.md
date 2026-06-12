# Publishing the Docs to GitHub Pages

The documentation site is built with MkDocs (Material) and deployed to **GitHub Pages**
by a CI workflow. The repository already ships
[`.github/workflows/pages.yml`](https://github.com/kotenev/archub_cms/blob/main/.github/workflows/pages.yml),
which uses the modern *GitHub Actions* Pages source — no `gh-pages` branch required.

## 1. One-time repository setup

In your repository on GitHub:

1. **Settings → Pages → Build and deployment → Source:** select **GitHub Actions**.
2. Make sure Actions are enabled (**Settings → Actions → General**).

That's it — the workflow already requests the right permissions (`pages: write`,
`id-token: write`).

## 2. Point the site at your repository

The published URL of a GitHub **project** site is
`https://<owner>.github.io/<repo>/`. Set `site_url` (and the repo links) in `mkdocs.yml`
to match your fork:

```yaml
site_url: https://<owner>.github.io/<repo>/
repo_url: https://github.com/<owner>/<repo>
repo_name: <owner>/<repo>
```

!!! warning "Match the actual remote"
    The committed config points at `kotenev/archub_cms`
    (`https://kotenev.github.io/archub_cms/`). If you fork or rename the repository,
    update `site_url`/`repo_url`/`repo_name` to your `<owner>/<repo>` so canonical links
    and the sitemap are correct. Internal navigation works regardless.

## 3. Deploy

Push to `main`, or run the workflow manually:

- **Automatic:** any push to `main` that touches `docs/**`, `mkdocs.yml`,
  `pyproject.toml`, `demo_site/**` or the workflow itself triggers a build + deploy.
- **Manual:** **Actions → Publish GitHub Pages → Run workflow** (`workflow_dispatch`).

Watch the run under the **Actions** tab. The `deploy` job prints the live URL, and the
**github-pages** environment on the repo home page links to it.

## What the workflow does

```yaml
# .github/workflows/pages.yml (essentials)
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - uses: actions/configure-pages@v5
      - run: python -m pip install -e .[docs]      # mkdocs + material + plantuml-markdown
      - run: mkdocs build --strict --site-dir site  # fails on broken links
      - run: |                                       # bundle the static demo under /demo
          mkdir -p site/demo && cp -R demo_site/. site/demo/
      - uses: actions/upload-pages-artifact@v3
        with: { path: site }
  deploy:
    needs: build
    steps:
      - uses: actions/deploy-pages@v4
```

The `.[docs]` extra installs everything needed, including `plantuml-markdown` so the
**C4 PlantUML** diagrams render to SVG at build time.

## Manual alternative — `mkdocs gh-deploy`

If you prefer to publish from your machine to a `gh-pages` branch (the classic flow):

```bash
python -m pip install -e .[docs]
mkdocs gh-deploy --strict   # builds and force-pushes to the gh-pages branch
```

Then set **Settings → Pages → Source: Deploy from a branch → `gh-pages` / `(root)`**.
Use the Actions workflow *or* `gh-deploy`, not both, to avoid fighting over the source.

## Building locally first

Always validate before pushing:

```bash
python -m pip install -e .[docs]
mkdocs serve              # live preview at http://127.0.0.1:8000
mkdocs build --strict     # exactly what CI runs
```

## PlantUML diagrams in CI

The [C4 diagrams](../architecture/c4-model.md) are rendered by `plantuml-markdown` via
the server set in `mkdocs.yml` (`https://www.plantuml.com/plantuml` by default). GitHub
runners have outbound network, so this works out of the box.

For **fully reproducible** builds that don't depend on a public service, self-host
PlantUML and point the config at it:

```yaml
# mkdocs.yml
markdown_extensions:
  - plantuml_markdown:
      server: http://localhost:8080   # your own PlantUML server
      format: svg
```

…or install the `plantuml` CLI (plus Java/Graphviz) on the runner and set `server: ""`
so the extension shells out locally. The `.puml` sources under `docs/diagrams/` can also
be pre-rendered with `plantuml -tsvg docs/diagrams/**/*.puml`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| 404 at the Pages URL | Settings → Pages → Source must be **GitHub Actions**; check the run succeeded. |
| CSS/links 404 under a subpath | Set `site_url` to the real `https://<owner>.github.io/<repo>/`. |
| Build fails on a broken link | `--strict` is intentional — fix the link, or run `mkdocs build` locally to find it. |
| Diagrams missing | Ensure `.[docs]` (with `plantuml-markdown`) installed and the PlantUML server is reachable. |
| Permission denied deploying | The workflow needs `pages: write` + `id-token: write` (already set). |
