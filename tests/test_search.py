"""Tests for the federated + faceted search context (Phase 17)."""

from __future__ import annotations

import pytest

from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.application.search_service import get_archub_search_service
from archub_cms.demo import seed_demo_content
from archub_cms.domain.search.facets import FacetBuilder
from archub_cms.domain.search.models import Facet, SearchQuery, SearchResultItem
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    service = get_archub_cms_service()
    seed_demo_content(service)
    return service


# --- domain: facets + query matching -------------------------------------


DOCS = [
    {"content_type_alias": "page", "space_key": "docs", "tags": ["a", "b"]},
    {"content_type_alias": "page", "space_key": "docs", "tags": ["b"]},
    {"content_type_alias": "rag_material", "space_key": "kb", "tags": ["a"]},
]


def test_facet_builder_counts():
    facets = {
        f.field: dict(f.buckets)
        for f in FacetBuilder.build(DOCS, fields=["content_type_alias", "tags"])
    }
    assert facets["content_type_alias"] == {"page": 2, "rag_material": 1}
    assert facets["tags"] == {"a": 2, "b": 2}


def test_facet_bucket_ordering_descending():
    docs = [{"k": "x"}, {"k": "x"}, {"k": "y"}]
    facet = FacetBuilder.build(docs, fields=["k"])[0]
    assert facet.buckets[0] == ("x", 2)


def test_search_query_filter_matching():
    q = SearchQuery(q="x", content_types=("page",), tags=("b",))
    assert q.matches(content_type="page", space="docs", tags=("a", "b"))
    assert not q.matches(content_type="rag_material", space="kb", tags=("b",))
    assert not q.matches(content_type="page", space="docs", tags=("a",))  # missing required tag b


def test_result_item_serialization():
    item = SearchResultItem(
        route_path="/cms/x", title="X", content_type_alias="page", score=1.234567
    )
    assert item.as_dict()["score"] == 1.2346
    assert isinstance(Facet("k").as_dict()["buckets"], list)


# --- application: federated search over real content ---------------------


def _service(cms):
    return get_archub_search_service(get_archub_knowledge_base_service(cms))


def test_federated_search_ranks_and_facets(cms):
    results = _service(cms).search(SearchQuery(q="ArcHub", limit=10))
    assert results.total >= 2
    # ranked descending by score
    scores = [item.score for item in results.items]
    assert scores == sorted(scores, reverse=True)
    facet_fields = {f.field for f in results.facets}
    assert {"content_type_alias", "space_key", "tags"} <= facet_fields


def test_search_filter_and_pagination(cms):
    svc = _service(cms)
    only_rag = svc.search(SearchQuery(q="", content_types=("rag_material",)))
    assert only_rag.total == 1
    assert all(i.content_type_alias == "rag_material" for i in only_rag.items)

    page1 = svc.search(SearchQuery(q="", limit=1, offset=0))
    page2 = svc.search(SearchQuery(q="", limit=1, offset=1))
    assert page1.total == page2.total
    assert len(page1.items) == 1
    assert page1.items[0].route_path != page2.items[0].route_path


# --- endpoints ------------------------------------------------------------


def test_search_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        get_res = client.get("/api/platform/search", params={"q": "ArcHub", "limit": 5})
        assert get_res.status_code == 200
        body = get_res.json()
        assert body["total"] >= 1 and "facets" in body

        filtered = client.get(
            "/api/platform/search", params={"content_types": "rag_material"}
        ).json()
        assert all(i["content_type_alias"] == "rag_material" for i in filtered["items"])

        post_res = client.post("/api/platform/search", json={"q": "developers", "limit": 3})
        assert post_res.status_code == 200 and "items" in post_res.json()
