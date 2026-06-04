from __future__ import annotations

from fastapi.testclient import TestClient

from archub_cms.app import create_archub_app
from archub_cms.application.delivery import DeliveryQuery, get_archub_delivery_service
from archub_cms.application.governance import get_archub_governance_service
from archub_cms.application.knowledge import KnowledgeQuery, get_archub_knowledge_base_service
from archub_cms.application.media import ArcHubMediaService, MediaPolicy, get_archub_media_service
from archub_cms.application.modeling import get_archub_modeling_service
from archub_cms.application.packages import get_archub_package_service
from archub_cms.application.plugins import ArcHubPluginRegistry
from archub_cms.application.publishing import get_archub_publishing_service
from archub_cms.application.versioning import get_archub_versioning_service
from archub_cms.application.webhooks import get_archub_webhook_service
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


def test_webhook_service_manages_subscriptions_and_dispatches_signed_deliveries(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    webhooks = get_archub_webhook_service(cms)

    subscription = webhooks.upsert(
        name="Published content hook",
        target_url="https://example.test/archub-webhook",
        events=["content.published"],
        secret="test-secret",
        actor="test",
    )
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Webhook service page",
        slug="webhook-service-page",
        payload={"title": "Webhook service page", "body": "<p>Webhook.</p>"},
        created_by="test",
    )

    get_archub_publishing_service(cms).publish(node.node_id, actor="test")
    pending = webhooks.deliveries(status="pending")
    sent: list[dict[str, object]] = []

    def sender(
        target_url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> int:
        sent.append(
            {
                "target_url": target_url,
                "payload": payload,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return 202

    dispatch = webhooks.dispatch_pending(actor="worker", sender=sender)

    assert subscription.events[0].event_type == "webhook.subscription.upserted"
    assert pending["total"] == 1
    assert dispatch.payload["processed_count"] == 1
    assert len(dispatch.payload["delivered"]) == 1
    assert dispatch.events[0].event_type == "webhook.dispatch.completed"
    assert sent[0]["target_url"] == "https://example.test/archub-webhook"
    assert sent[0]["headers"]["X-ArcHub-Event"] == "content.published"
    assert str(sent[0]["headers"]["X-ArcHub-Signature"]).startswith("sha256=")


def test_governance_service_controls_editor_permissions_and_public_access(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    governance = get_archub_governance_service(cms)
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Governance service page",
        slug="governance-service-page",
        payload={"title": "Governance service page", "body": "<p>Governed.</p>"},
        created_by="test",
    )

    grant = governance.grant_permission(
        subject="editor@example.test",
        scope_node_id=node.node_id,
        actions=["browse", "update"],
        include_descendants=True,
        actor="admin",
    )
    access = governance.set_public_access_rule(
        node.node_id,
        policy="members",
        member_groups=["premium"],
        login_path="/login",
        actor="admin",
    )

    assert grant.events[0].event_type == "governance.permission.granted"
    assert governance.can_user_perform(
        username="editor@example.test",
        is_admin=False,
        action="update",
        node_id=node.node_id,
    )
    assert access.payload["policy"] == "members"
    assert not governance.can_access_public_content(node.node_id, authenticated=False)
    assert governance.can_access_public_content(
        node.node_id,
        username="member@example.test",
        authenticated=True,
        member_groups=["premium"],
    )
    removed = governance.remove_public_access_rule(node.node_id, actor="admin")

    assert removed.events[0].event_type == "governance.public_access.removed"
    assert governance.public_access_rule(node.node_id)["policy"] == "public"


def test_modeling_service_manages_schema_compositions_and_blueprints(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    modeling = get_archub_modeling_service(cms)

    data_type = modeling.upsert_data_type(
        alias="short_text",
        name="Short text",
        editor="text",
        validation={"maxLength": 120},
        actor="modeler",
    )
    composition = modeling.upsert_composition(
        alias="seo_meta",
        name="SEO metadata",
        fields=[
            {
                "alias": "seo_title",
                "name": "SEO title",
                "editor": "text",
                "data_type_alias": "short_text",
            }
        ],
        actor="modeler",
    )
    content_type = modeling.upsert_content_type(
        alias="landing_page",
        name="Landing page",
        icon="landing",
        fields=[
            {
                "alias": "title",
                "name": "Title",
                "editor": "text",
                "required": True,
                "data_type_alias": "short_text",
            }
        ],
        composition_aliases=["seo_meta"],
        allow_at_root=True,
        template="page",
        actor="modeler",
    )
    blueprint = modeling.upsert_blueprint(
        content_type_alias="landing_page",
        name="Campaign landing page",
        payload={"title": "Campaign", "seo_title": "Campaign SEO"},
        actor="modeler",
    )
    report = modeling.report()

    assert data_type.events[0].event_type == "content_model.data_type.upserted"
    assert composition.events[0].event_type == "content_model.composition.upserted"
    assert content_type.events[0].event_type == "content_model.type.upserted"
    assert blueprint.events[0].event_type == "content_model.blueprint.upserted"
    assert blueprint.payload["payload"]["seo_title"] == "Campaign SEO"
    assert report["composed_content_types"] >= 1
    assert any(item["alias"] == "landing_page" for item in report["content_types"])


def test_versioning_service_restores_and_cleans_old_versions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    cms = get_archub_cms_service()
    versioning = get_archub_versioning_service(cms)
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Versioned page",
        slug="versioned-page",
        payload={"title": "Versioned page", "body": "<p>v1</p>"},
        created_by="author",
    )
    for index in range(2, 6):
        cms.update_node(
            node.node_id,
            name="Versioned page",
            slug="versioned-page",
            payload={"title": "Versioned page", "body": f"<p>v{index}</p>"},
            updated_by="author",
        )

    versions = versioning.versions(node.node_id, limit=20)
    oldest = versions["items"][-1]
    restored = versioning.restore(
        node.node_id,
        oldest["version_no"],
        actor="editor",
    )
    after_restore = versioning.versions(node.node_id, limit=20)
    cleanup = versioning.cleanup(
        node_id=node.node_id,
        keep_latest=2,
        older_than_seconds=None,
        actor="maintenance",
    )

    assert restored.events[0].event_type == "content.version.restored"
    assert cms.get_node(node.node_id).draft["body"] == "<p>v1</p>"
    assert cleanup.events[0].event_type == "content.versions.cleaned"
    assert cleanup.payload["deleted_count"] == after_restore["total"] - 2
    assert versioning.versions(node.node_id, limit=20)["total"] == 2


def test_knowledge_platform_discovers_plugins_graph_and_offline_answers(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    seed_demo_content()
    plugin_dir = tmp_path / "plugins" / "macro-test"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        """
        {
          "id": "acme.macro.decision-log",
          "name": "Decision Log Macro",
          "version": "1.2.0",
          "capability": "macro",
          "runtime": "http",
          "entrypoint": "https://plugins.example.test/decision-log",
          "description": "Embeds ADR summaries in knowledge pages.",
          "permissions": ["content:read"],
          "tags": ["adr", "confluence"]
        }
        """,
        encoding="utf-8",
    )
    cms = get_archub_cms_service()
    space = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Engineering KB",
        slug="engineering",
        payload={
            "title": "Engineering KB",
            "summary": "Engineering knowledge space.",
            "body": "<p>Team knowledge root.</p>",
        },
        created_by="editor",
    )
    cms.publish_node(space.node_id, published_by="editor")
    incident = cms.create_node(
        parent_id=space.node_id,
        content_type_alias="knowledge_article",
        name="Incident process",
        slug="incident-process",
        payload={
            "title": "Incident process",
            "excerpt": "How engineering handles incidents.",
            "body": (
                "Incident response uses severity, owner, timeline and follow-up actions. "
                "See [[engineering/postmortems]] and /cms/engineering/missing-runbook."
            ),
            "tags": "incident,runbook",
        },
        created_by="editor",
    )
    cms.publish_node(incident.node_id, published_by="editor")
    postmortems = cms.create_node(
        parent_id=space.node_id,
        content_type_alias="knowledge_article",
        name="Postmortems",
        slug="postmortems",
        payload={
            "title": "Postmortems",
            "excerpt": "Template for incident learning.",
            "body": "Postmortems capture impact, root cause, timeline and action items.",
            "tags": "incident,template",
        },
        created_by="editor",
    )
    cms.publish_node(postmortems.node_id, published_by="editor")

    service = get_archub_knowledge_base_service(
        cms,
        plugin_registry=ArcHubPluginRegistry(plugin_dirs=(tmp_path / "plugins",)),
    )
    documents = service.documents(KnowledgeQuery(q="incident", space_key="engineering"))
    graph = service.graph(space_key="engineering")
    answer = service.answer("How do we handle incidents?", space_key="engineering")
    vault = service.vault_export(space_key="engineering")
    plugins = service.plugin_catalog()

    assert documents["total"] >= 2
    assert graph.as_dict()["edge_count"] >= 2
    assert graph.as_dict()["unresolved_count"] == 1
    assert answer.provider == "offline-extractive"
    assert answer.sources
    assert vault["format"] == "obsidian-compatible-markdown-vault"
    assert any(item["path"].endswith("incident-process.md") for item in vault["files"])
    assert any(item["plugin_id"] == "acme.macro.decision-log" for item in plugins["plugins"])
    assert plugins["capability_counts"]["llm_provider"] >= 2
