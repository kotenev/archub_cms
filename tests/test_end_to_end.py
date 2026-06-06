"""End-to-end integration: prove the bounded contexts compose into a platform.

Each context is unit-tested in isolation elsewhere; these tests exercise a
realistic corporate-knowledge-base scenario across many contexts at once via the
``ArcHubPlatform`` facade and the command services, asserting cross-context
visibility (publish → delivery/knowledge/search/graph; watch → inbox; etc.).
"""

from __future__ import annotations

import pytest

from archub_cms.application.agent_service import get_archub_agent_service
from archub_cms.application.collaboration_service import get_archub_collaboration_service
from archub_cms.application.governance_service import (
    AccessControlService,
    GovernanceCommandService,
)
from archub_cms.application.ingestion_service import get_archub_ingestion_service
from archub_cms.application.localization_service import LocalizationCommandService
from archub_cms.application.modeling_service import ModelingCommandService
from archub_cms.application.packaging_service import get_archub_packaging_service
from archub_cms.application.platform import ArcHubPlatform
from archub_cms.application.subscription_service import SubscriptionCommandService
from archub_cms.application.versioning_service import VersioningQueryService
from archub_cms.application.workflow_service import WorkflowCommandService
from archub_cms.domain.search.models import SearchQuery
from archub_cms.extensibility.host import PluginHost
from archub_cms.infrastructure.sqlite.versioning_repository import CmsVersioningRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def platform(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    host = PluginHost().load()
    return ArcHubPlatform(cms=cms, plugin_host=host)


# --- authoring lifecycle across modeling/content/workflow/i18n/delivery ---


def test_authoring_lifecycle_is_visible_everywhere(platform):
    cms = platform.cms

    # 1. modeling: define a content type allowed at root
    ModelingCommandService(cms=cms).upsert_content_type(
        alias="guide",
        name="Guide",
        fields=[{"alias": "body", "name": "Body"}],
        allow_at_root=True,
        actor="admin",
    )
    assert platform.modeling.content_type("guide") is not None

    # 2. content: author pages (a knowledge content type) with a wiki-link
    parent = platform.content.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Onboarding",
        slug="onboarding",
        payload={"title": "Onboarding", "body": "Start with [[setup]]."},
        created_by="alice",
    )
    child = platform.content.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Setup",
        slug="setup",
        payload={"title": "Setup", "body": "Install steps."},
        created_by="alice",
    )

    # 3. workflow: drive the approval state machine
    wf = WorkflowCommandService(cms=cms)
    wf.transition(parent.node_id, "in_review", actor="alice")
    wf.transition(parent.node_id, "approved", actor="lead")
    assert platform.workflow.get(parent.node_id)["state"] == "approved"

    # 4. localization: add a French variant
    LocalizationCommandService(cms=cms).upsert_variant(
        parent.node_id, culture="fr-FR", payload={"title": "Intégration"}, actor="alice"
    )
    assert platform.localization.cultures(parent.node_id)["cultures"]

    # 5. publish both nodes
    platform.content.publish_node(parent.node_id, published_by="lead")
    platform.content.publish_node(child.node_id, published_by="lead")

    # 6. delivery: published nodes appear in the sitemap
    routes = {e["loc"] for e in platform.delivery.sitemap()["items"]}
    assert "/cms/onboarding" in routes and "/cms/setup" in routes

    # 7. knowledge + search: discoverable via federated faceted search
    assert platform.knowledge.documents()["total"] >= 2
    results = platform.search.search(SearchQuery(q="setup"))
    assert any(i.route_path == "/cms/setup" for i in results.items)

    # 8. graph: the [[setup]] wiki-link is a resolved backlink
    backlinks = platform.graph.backlinks("/cms/setup")
    assert "/cms/onboarding" in backlinks["backlinks"]


# --- collaboration + governance + subscriptions compose -------------------


def test_collaboration_governance_and_watching(platform):
    cms = platform.cms
    page = platform.content.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Policy",
        slug="policy",
        payload={"title": "Policy"},
        created_by="alice",
    )

    # collaboration: comment with a mention
    collab = get_archub_collaboration_service(db_path=cms.db_path)
    comment = collab.add_comment(node_id=page.node_id, author="alice", body="Please review @bob")
    assert "bob" in [m.username for m in comment.mentions]

    # governance: members-only access, checked through the aggregate
    gov = GovernanceCommandService(cms=cms)
    gov.set_access_rule(
        node_id=page.node_id, policy="members", member_groups=["staff"], actor="admin"
    )
    acl = AccessControlService(cms=cms)
    assert acl.can_access(page.node_id, authenticated=False)["allowed"] is False
    assert acl.can_access(page.node_id, authenticated=True, groups=["staff"])["allowed"] is True

    # subscriptions: bob watches the page, then a publish lands in his inbox
    SubscriptionCommandService(cms=cms).watch(subscriber="bob", node_id=page.node_id)
    platform.content.publish_node(page.node_id, published_by="alice")
    inbox = platform.subscriptions.inbox("bob")
    assert any(item["action"] == "content.published" for item in inbox["items"])


# --- migration + intelligence + packaging + versioning + analytics --------


def test_migration_intelligence_and_packaging(platform):
    cms, host = platform.cms, platform.plugin_host

    # ingestion: import a markdown vault via the importer plugin, published
    ingest = get_archub_ingestion_service(content=platform.content, plugin_host=host)
    res = ingest.import_markdown(
        [
            {"path": "kb/runbook.md", "content": "# Runbook\nHow to deploy the service."},
            {"path": "kb/faq.md", "content": "# FAQ\nCommon questions."},
        ],
        publish=True,
        actor="migrator",
    )
    assert res["created_count"] == 2

    # search finds the imported content
    hits = platform.search.search(SearchQuery(q="deploy"))
    assert any(i.route_path == "/cms/runbook" for i in hits.items)

    # agentic answering with a tool over the imported KB
    agent = get_archub_agent_service(knowledge=platform.knowledge, plugin_host=host)
    agent_answer = agent.answer("How do we deploy?", tools=("summarize",))
    assert agent_answer["sources"]
    assert any(t["name"] == "summarize" for t in agent_answer["tools_used"])

    # versioning: edit a node, diff shows the change
    runbook = cms.get_published_by_path("/cms/runbook")
    cms.update_node(
        runbook.node_id,
        name="Runbook",
        slug="runbook",
        payload={"title": "Runbook v2", "body": "Updated."},
        updated_by="migrator",
    )
    versions = VersioningQueryService(CmsVersioningRepository(cms))
    nos = sorted(v["version_no"] for v in versions.history(runbook.node_id)["items"])
    diff = versions.diff(runbook.node_id, from_version_no=nos[0], to_version_no=nos[-1])
    assert diff["summary"]["changed"] >= 1

    # packaging: export everything, then inspect the bundle
    pkg = get_archub_packaging_service(cms=cms).export(name="KB bundle", actor="admin")
    assert pkg.is_supported and pkg.summary()["nodes"] >= 2
    inspection = get_archub_packaging_service(cms=cms).inspect(pkg.data)
    assert inspection.ok

    # analytics: the platform reports healthy content and lists all contexts
    health = platform.analytics.health()
    assert health["grade"] in {"A", "B", "C", "D", "F"}
    caps = platform.capabilities()
    assert caps["context_count"] == 17
    assert caps["plugins"]["loaded"] >= 9
