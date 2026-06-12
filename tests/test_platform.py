"""Tests for the DDD refactor, plugin runtime and hybrid RAG (Phase 1)."""

from __future__ import annotations

import pytest

from archub_cms.application.content_service import get_archub_content_service
from archub_cms.application.embeddings import HashingEmbedder, cosine_similarity
from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.demo import seed_demo_content
from archub_cms.domain.content.events import CONTENT_PUBLISHED
from archub_cms.domain.content.node import ContentNode, NodeStatus
from archub_cms.domain.content.value_objects import Culture, RoutePath, Slug
from archub_cms.extensibility.host import PluginHost
from archub_cms.extensibility.permissions import PermissionGate
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.content_repository import SqliteContentRepository
from archub_cms.infrastructure.sqlite.embedding_repository import SqliteEmbeddingRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service
from archub_cms.settings import ArcHubSettings


@pytest.fixture(autouse=True)
def _clean_bus():
    # The event bus is process-global; reset subscriptions between tests so
    # plugin handlers from one test don't pile up on the next.
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    service = get_archub_cms_service()
    seed_demo_content(service)
    return service


# --- domain: value objects & aggregate -----------------------------------


def test_slug_normalizes_and_roots():
    assert Slug.create("Hello World!").value == "hello-world"
    assert Slug.create("  ").value == "content"
    assert Slug.root().is_root


def test_route_path_composition_and_space():
    assert RoutePath.compose("/cms", Slug("docs")).value == "/cms/docs"
    assert RoutePath.compose(None, Slug.root()).value == "/cms"
    assert RoutePath("/cms/team/page").space_segment == "team"


def test_culture_parsing():
    assert Culture.parse("fr-fr").value == "fr-FR"
    assert Culture.parse("").is_invariant
    with pytest.raises(ValueError):
        Culture.parse("not a locale")


def test_content_node_publish_guard():
    node = ContentNode(
        node_id="n1",
        parent_id="root",
        content_type_alias="page",
        name="Page",
        slug=Slug("page"),
        route_path=RoutePath("/cms/page"),
        level=1,
        status=NodeStatus.DRAFT,
        draft={"title": "Page"},
    )
    assert node.can_publish().ok
    node.draft = {}
    assert not node.can_publish().ok


# --- infrastructure: content repository ----------------------------------


def test_content_repository_reads_tree(cms):
    repo = SqliteContentRepository(Database(cms.db_path))
    routes = {node.route_path.value for node in repo.list_tree()}
    assert "/cms" in routes and "/cms/demo" in routes
    demo = repo.get_by_route("/cms/demo")
    assert demo is not None and demo.is_published


# --- application: content service emits events ----------------------------


def test_content_service_publish_emits_event(cms):
    fired: list[str] = []
    get_event_bus().subscribe(CONTENT_PUBLISHED, lambda event: fired.append(event.aggregate_id))

    service = get_archub_content_service(cms=cms)
    node = service.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Eventful",
        slug="eventful",
        payload={"title": "Eventful", "body": "<p>x</p>"},
        created_by="test",
    )
    assert isinstance(node, ContentNode)
    published = service.publish_node(node.node_id, published_by="test")
    assert published.is_published
    assert node.node_id in fired


# --- extensibility: plugin runtime ---------------------------------------


def _host(cms, *, gate: PermissionGate | None = None) -> PluginHost:
    settings = ArcHubSettings.from_env()
    return PluginHost(settings=settings, permission_gate=gate).load()


def test_plugin_host_loads_example_and_hook_fires(cms):
    host = _host(cms)
    loaded = {item["plugin_id"] for item in host.report()["loaded"]}
    assert "example.backlinks" in loaded

    cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Hooked",
        slug="hooked",
        payload={"title": "Hooked", "body": "<p>hi</p>"},
        created_by="test",
    )
    node = cms.find_node_by_field("page", "title", "Hooked")
    cms.publish_node(node.node_id, published_by="test")

    report = host.report()
    assert report["hook_counts"].get(CONTENT_PUBLISHED, 0) >= 1
    hits = host.search("hooked", limit=5)
    assert any(hit.route_path == "/cms/hooked" for hit in hits)


def test_plugin_host_denies_permissions(cms):
    host = _host(cms, gate=PermissionGate(allowed=set()))
    report = host.report()
    assert "example.backlinks" not in {item["plugin_id"] for item in report["loaded"]}
    assert any(f["plugin_id"] == "example.backlinks" for f in report["failures"])


# --- RAG: embeddings + hybrid search -------------------------------------


def test_hashing_embedder_is_deterministic_and_normalized():
    emb = HashingEmbedder(dim=64)
    a = emb.embed("knowledge base platform")
    b = emb.embed("knowledge base platform")
    assert a == b
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)
    c = emb.embed("completely different unrelated tokens")
    assert cosine_similarity(a, c) < 0.9


def test_embedding_repository_indexes_and_queries(cms):
    repo = SqliteEmbeddingRepository(Database(cms.db_path), HashingEmbedder(dim=128))
    repo.index("/cms/a", "headless cms content delivery api")
    repo.index("/cms/b", "vedic astrology birth chart")
    results = repo.query("headless cms api", limit=2)
    assert results[0][0] == "/cms/a"
    assert repo.count() == 2


def test_hybrid_search_ranks_relevant_document(cms):
    service = get_archub_knowledge_base_service(cms)
    hits = service.hybrid_search("headless CMS for developers", limit=5)
    assert hits
    assert hits[0].route_path == "/cms/developers"


def test_hybrid_search_merges_plugin_hits(cms):
    host = _host(cms)
    # Publish so the example plugin records a route to contribute.
    cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Pluginic",
        slug="pluginic",
        payload={"title": "Pluginic", "body": "<p>z</p>"},
        created_by="test",
    )
    node = cms.find_node_by_field("page", "title", "Pluginic")
    cms.publish_node(node.node_id, published_by="test")

    service = get_archub_knowledge_base_service(cms, plugin_host=host)
    hits = service.hybrid_search("pluginic", limit=10)
    assert any(hit.route_path == "/cms/pluginic" for hit in hits)


# --- web: platform endpoints ---------------------------------------------


def test_platform_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        plugins = client.get("/api/platform/plugins")
        assert plugins.status_code == 200
        assert "example.backlinks" in {p["plugin_id"] for p in plugins.json()["loaded"]}

        search = client.get("/api/platform/knowledge/search", params={"q": "developers"})
        assert search.status_code == 200
        assert search.json()["total"] >= 1

        answer = client.post("/api/platform/knowledge/answer", json={"question": "What is ArcHub?"})
        assert answer.status_code == 200
        assert answer.json()["sources"]
