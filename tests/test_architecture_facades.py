from __future__ import annotations

from fastapi.testclient import TestClient

from archub_cms.app import create_archub_app
from archub_cms.application.delivery import DeliveryQuery, get_archub_delivery_service
from archub_cms.demo import seed_demo_content
from archub_cms.published import ArcHubContentHelper
from archub_cms.services.cms import get_archub_cms_service
from archub_cms.services.jobs import ArcHubMaintenanceService
from archub_cms.settings import ArcHubSettings


def test_published_content_helper_reads_content_children_and_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()

    helper = ArcHubContentHelper()
    root = helper.content("/cms")
    demo = helper.content("/cms/demo")

    assert root is not None
    assert demo is not None
    assert root.route_path == "/cms"
    assert demo.value("title") == "ArcHub CMS demo"
    assert demo.has_value("builder_blocks")
    assert "/cms/demo" in {child.route_path for child in root.children()}
    assert "archub-builder-content" in helper.render_content_blocks(demo)


def test_published_content_helper_resolves_dictionary_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    cms.upsert_dictionary_item(
        item_key="WelcomeText",
        group_name="site",
        values={"en": "Welcome", "fr-FR": "Bienvenue", "default": "Hello"},
        updated_by="test",
    )

    helper = ArcHubContentHelper(cms)

    assert helper.dictionary_value("WelcomeText", culture="fr-FR") == "Bienvenue"
    assert helper.dictionary_value("WelcomeText", culture="en-US") == "Welcome"
    assert helper.dictionary_value("Missing", default="fallback") == "fallback"


def test_maintenance_service_runs_due_work_without_external_scheduler(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    settings = ArcHubSettings(webhook_dispatch_limit=5)

    report = ArcHubMaintenanceService(cms=cms, settings=settings).run_once(actor="test")

    assert "workflow" in report
    assert "webhooks" in report
    assert "runtime_status" in report
    assert report["webhooks"]["processed_count"] == 0
    assert report["health"]["error_count"] == 0


def test_delivery_service_limits_fields_and_expands_content_references(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    related = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Related content",
        slug="related-content",
        payload={
            "title": "Related content",
            "summary": "/cms/developers",
            "body": "<p>Reference test.</p>",
        },
        created_by="test",
    )
    cms.publish_node(related.node_id, published_by="test")

    payload = get_archub_delivery_service(cms).content(
        "/cms/related-content",
        DeliveryQuery(fields="title,summary", expand="properties[summary]"),
    )

    assert payload is not None
    assert set(payload["payload"]) == {"title", "summary"}
    assert payload["payload"]["summary"]["route_path"] == "/cms/developers"
    assert payload["payload"]["summary"]["payload"]["title"] == "For developers"


def test_delivery_api_supports_fields_expand_and_start_item(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()

    app = create_archub_app()
    with TestClient(app) as client:
        content_response = client.get("/cms/api/content/demo?fields=title")
        tree_response = client.get("/cms/api/tree", headers={"Start-Item": "/cms/demo"})

    assert content_response.status_code == 200
    assert content_response.json()["payload"] == {"title": "ArcHub CMS demo"}
    assert tree_response.status_code == 200
    assert tree_response.json()["route_path"] == "/cms/demo"
