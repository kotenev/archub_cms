# GitHub Demo Site

The repository includes a static GitHub Pages demo under `demo_site/`.

It is intentionally static: GitHub Pages cannot run the FastAPI backoffice, so
the static demo explains the product and links to the local live demo commands.

The live demo is the FastAPI app:

```bash
python -m pip install -e .[server]
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

The GitHub Pages workflow copies `demo_site/` and the MkDocs output into the
published site artifact.
