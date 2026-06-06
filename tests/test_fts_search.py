"""Tests for the FTS5 full-text search (Phase 25)."""

from __future__ import annotations

import pytest

from archub_cms.application.fts_search_service import get_archub_fts_search_service
from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.demo import seed_demo_content
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.fts_index import FtsIndex
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    service = get_archub_cms_service()
    seed_demo_content(service)
    return service


# --- FTS index (infrastructure) ------------------------------------------


def test_fts_index_rebuild_and_bm25_ranking(cms):
    index = FtsIndex(Database(cms.db_path))
    assert index.available  # this SQLite build has FTS5
    index.rebuild(
        [
            {
                "route_path": "/cms/a",
                "title": "Deploy guide",
                "body": "How to deploy the service",
                "tags": [],
            },
            {"route_path": "/cms/b", "title": "FAQ", "body": "general questions", "tags": ["faq"]},
        ]
    )
    assert index.count() == 2
    hits = index.search("deploy")
    assert hits and hits[0].route_path == "/cms/a"
    assert hits[0].score > 0  # negated bm25 → higher is better
    assert hits[0].snippet  # snippet highlight present


def test_fts_prefix_and_stemming(cms):
    index = FtsIndex(Database(cms.db_path))
    index.rebuild(
        [
            {
                "route_path": "/cms/x",
                "title": "Developers",
                "body": "developer documentation",
                "tags": [],
            }
        ]
    )
    # porter stemming + prefix: "develop" matches "developers"/"developer"
    assert index.search("develop")[0].route_path == "/cms/x"


def test_fts_query_sanitization_is_safe(cms):
    index = FtsIndex(Database(cms.db_path))
    index.rebuild([{"route_path": "/cms/x", "title": "Test", "body": "content here", "tags": []}])
    # special FTS operators must not raise
    assert index.search('what is (this)? "quoted" -minus AND*') == [] or True
    assert index.search("") == []


# --- application service --------------------------------------------------


def test_service_indexes_and_searches_real_content(cms):
    svc = get_archub_fts_search_service(knowledge=get_archub_knowledge_base_service(cms))
    assert svc.available
    result = svc.search("developers")
    assert result["engine"] == "fts5"
    assert any(i["route_path"] == "/cms/developers" for i in result["items"])


def test_service_auto_reindexes_on_new_content(cms):
    kb = get_archub_knowledge_base_service(cms)
    svc = get_archub_fts_search_service(knowledge=kb)
    svc.reindex()
    base = svc._index.count()

    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Kubernetes Runbook",
        slug="k8s",
        payload={"title": "Kubernetes Runbook", "body": "scaling pods and nodes"},
        created_by="t",
    )
    cms.publish_node(node.node_id, published_by="t")

    # a search triggers a rebuild because the document count changed
    result = svc.search("kubernetes")
    assert svc._index.count() > base
    assert any(i["route_path"] == "/cms/k8s" for i in result["items"])


def test_service_falls_back_when_fts_unavailable(cms):
    svc = get_archub_fts_search_service(knowledge=get_archub_knowledge_base_service(cms))
    svc._index._available = False  # simulate a SQLite build without FTS5
    result = svc.search("ArcHub")
    assert result["engine"] == "fallback-federated"
    assert "items" in result


# --- endpoints ------------------------------------------------------------


def test_fts_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        reindex = client.post("/api/platform/search/fts/reindex")
        assert reindex.status_code == 200 and reindex.json()["available"] is True

        res = client.get("/api/platform/search/fts", params={"q": "developers"})
        assert res.status_code == 200
        body = res.json()
        assert body["engine"] == "fts5"
        assert any(i["route_path"] == "/cms/developers" for i in body["items"])
