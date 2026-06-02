# ArcHub CMS 0.1.0

ArcHub CMS 0.1.0 is the first standalone product release prepared from the
Vedic Jyotish bot web backoffice.

## Highlights

- Headless CMS with document types, data types, templates and content tree.
- Draft/publish workflow, version history, preview tokens and public delivery.
- Content Builder block registry and public HTML renderer.
- Published content APIs: tree, content, search, tags, RSS and sitemap.
- Runtime content export for bot resources and RAG materials.
- Standalone FastAPI demo app with seeded content.
- GitHub Pages documentation and static demo site.

## Run locally

```bash
python -m pip install -e .[server]
uvicorn archub_cms.app:create_archub_app --factory --host 127.0.0.1 --port 8088
```

Open:

- Backoffice: `http://127.0.0.1:8088/admin/archub`
- Published site: `http://127.0.0.1:8088/cms`
- API docs: `http://127.0.0.1:8088/api/docs`

## License

Apache License, Version 2.0.
