from __future__ import annotations

from fastapi.testclient import TestClient

from archub_cms.app import create_archub_app
from archub_cms.application.delivery import DeliveryQuery, get_archub_delivery_service
from archub_cms.application.media import ArcHubMediaService, MediaPolicy, get_archub_media_service
from archub_cms.application.packages import get_archub_package_service
from archub_cms.application.publishing import get_archub_publishing_service
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


def test_publishing_service_emits_events_and_refreshes_runtime_export(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Publishing service page",
        slug="publishing-service-page",
        payload={"title": "Publishing service page", "body": "<p>Service test.</p>"},
        created_by="test",
    )

    result = get_archub_publishing_service(cms).publish(node.node_id, actor="test")

    assert result.node is not None
    assert result.node.is_published
    assert result.events[0].event_type == "content.published"
    assert result.runtime_exported
    assert cms.published_content_payload("/cms/publishing-service-page") is not None


def test_publishing_service_applies_due_workflow_with_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Scheduled service page",
        slug="scheduled-service-page",
        payload={"title": "Scheduled service page", "body": "<p>Scheduled.</p>"},
        created_by="test",
    )
    publishing = get_archub_publishing_service(cms)
    publishing.update_workflow(
        node_id=node.node_id,
        state="scheduled",
        scheduled_publish_at=1.0,
        actor="test",
    )

    result = publishing.apply_due_workflows(actor="test")
    updated = cms.get_node(node.node_id)

    assert result.report["applied_count"] == 1
    assert [event.event_type for event in result.events] == ["content.published"]
    assert result.runtime_exported
    assert updated is not None
    assert updated.is_published


def test_media_service_validates_policy_and_reports_usage_duplicates_orphans(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    media = ArcHubMediaService(
        cms,
        policy=MediaPolicy(allowed_content_types=("image/*", "application/pdf")),
    )

    try:
        media.register_reference(
            filename="hero.jpg",
            original_name="hero.jpg",
            content_type="image/jpeg",
            url="/media/hero.jpg",
            alt_text="",
            created_by="test",
        )
    except ValueError as exc:
        assert "alt text" in str(exc)
    else:
        raise AssertionError("Image without alt text should fail media policy")

    media.register_reference(
        filename="hero.jpg",
        original_name="hero.jpg",
        content_type="image/jpeg",
        url="/media/hero.jpg",
        folder="campaigns/2026",
        alt_text="Hero image",
        tags=["hero"],
        created_by="test",
    )
    media.register_reference(
        filename="hero-copy.jpg",
        original_name="hero.jpg",
        content_type="image/jpeg",
        url="/media/hero-copy.jpg",
        folder="campaigns/2026",
        alt_text="Hero duplicate",
        tags=["hero"],
        created_by="test",
    )
    cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Media usage page",
        slug="media-usage-page",
        payload={"title": "Media usage page", "body": '<img src="/media/hero.jpg">'},
        created_by="test",
    )

    report = media.library_report()
    payload = report.as_dict()

    assert payload["folders"][0]["folder"] == "campaigns/2026"
    assert payload["duplicates"][0]["count"] == 2
    assert any(asset["usage_count"] == 1 for asset in payload["assets"])
    assert any(asset["orphaned"] for asset in payload["assets"])


def test_media_admin_api_returns_dam_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    get_archub_media_service().register_reference(
        filename="guide.pdf",
        original_name="guide.pdf",
        content_type="application/pdf",
        url="/media/guide.pdf",
        folder="docs",
        created_by="test",
    )

    app = create_archub_app(seed_demo=False)
    with TestClient(app) as client:
        response = client.get("/admin/archub/media.json")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["assets"][0]["filename"] == "guide.pdf"
    assert data["policy"]["allowed_content_types"]


def test_package_service_exports_plans_and_imports_with_domain_events(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    package_service = get_archub_package_service(cms)

    export_result = package_service.export(
        name="Architecture package",
        node_ids=["root"],
        include_descendants=False,
        exported_by="test",
    )
    plan_result = package_service.plan_import(
        export_result.payload,
        overwrite=True,
        actor="test",
    )
    import_result = package_service.import_package(
        export_result.payload,
        overwrite=True,
        imported_by="test",
    )

    assert export_result.events[0].event_type == "package.exported"
    assert plan_result.events[0].event_type == "package.import.planned"
    assert import_result.events[0].event_type == "package.imported"
    assert export_result.payload["summary"]["ok"]
    assert plan_result.payload["inspection"]["ok"]
    assert import_result.payload["ok"]
