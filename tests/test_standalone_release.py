from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from archub_cms.app import create_archub_app
from archub_cms.demo import seed_demo_content
from archub_cms.services.cms import get_archub_cms_service


def test_seed_demo_content_publishes_demo_pages(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()

    report = seed_demo_content()
    cms = get_archub_cms_service()

    assert report["created"] >= 3
    assert cms.published_content_payload("/cms") is not None
    assert cms.published_content_payload("/cms/demo") is not None
    assert cms.published_content_payload("/cms/developers") is not None
    assert cms.search_published_rag_materials("demo", "ArcHub")


def test_create_archub_app_includes_backoffice_and_delivery_routes() -> None:
    app = create_archub_app(seed_demo=False)
    paths = {str(getattr(route, "path", "")) for route in app.routes}

    assert "/admin/archub" in paths
    assert "/cms" in paths
    assert "/cms/api/tree" in paths
    assert "/static" in paths


def test_demo_app_serves_backoffice_and_published_site(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()

    app = create_archub_app()
    with TestClient(app) as client:
        public_response = client.get("/cms")
        admin_response = client.get("/admin/archub")
        tree_response = client.get("/cms/api/tree")

    assert public_response.status_code == 200
    assert "ArcHub CMS" in public_response.text
    assert admin_response.status_code == 200
    assert tree_response.status_code == 200
    assert tree_response.json()["route_path"] == "/cms"


def test_product_sources_do_not_import_original_host() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "archub_cms"
    haystack = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.py"))

    assert "botplatform." not in haystack
    assert "products.jyotish" not in haystack
    assert "apps.bot" not in haystack
