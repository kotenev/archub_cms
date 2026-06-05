"""Tests for the knowledge-graph context (Phase 12)."""

from __future__ import annotations

import pytest

from archub_cms.application.graph_service import get_archub_graph_service
from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.domain.graph.analyzer import GraphAnalyzer
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    return get_archub_cms_service()


# --- pure domain: GraphAnalyzer ------------------------------------------

NODES = [("/cms/a", "A"), ("/cms/b", "B"), ("/cms/c", "C"), ("/cms/lonely", "L")]
EDGES = [
    ("/cms/a", "/cms/b", False),
    ("/cms/c", "/cms/b", False),
    ("/cms/b", "/cms/missing", True),  # broken
]


def test_backlinks_index():
    gz = GraphAnalyzer(NODES, EDGES)
    assert gz.backlinks_for("/cms/b") == ["/cms/a", "/cms/c"]
    assert gz.backlinks_for("/cms/b/") == ["/cms/a", "/cms/c"]  # normalized
    assert gz.backlinks_for("/cms/a") == []


def test_orphans_and_metrics():
    gz = GraphAnalyzer(NODES, EDGES)
    assert gz.orphans() == ["/cms/lonely"]
    m = gz.metrics()
    assert m.node_count == 4
    assert m.edge_count == 3
    assert m.orphan_count == 1
    assert m.broken_link_count == 1
    assert m.authorities[0] == ("/cms/b", 2)  # most backlinked
    assert ("/cms/a", 1) in m.hubs


def test_canvas_layout_and_weight():
    canvas = GraphAnalyzer(NODES, EDGES).canvas().as_dict()
    assert canvas["node_count"] == 4
    assert canvas["edge_count"] == 3
    weights = {n["route_path"]: n["weight"] for n in canvas["nodes"]}
    assert weights["/cms/b"] == 2  # two backlinks → heaviest
    assert weights["/cms/lonely"] == 0
    # nodes carry deterministic positions
    assert all("x" in n and "y" in n for n in canvas["nodes"])


def test_empty_graph_is_safe():
    gz = GraphAnalyzer([], [])
    assert gz.orphans() == []
    assert gz.canvas().as_dict()["node_count"] == 0
    assert gz.metrics().node_count == 0


# --- application service over real content -------------------------------


def _service(cms):
    return get_archub_graph_service(get_archub_knowledge_base_service(cms))


def test_overview_and_canvas_over_linked_content(cms):
    parent = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Parent",
        slug="parent",
        payload={"title": "Parent", "body": "See [[child]] for details."},
        created_by="t",
    )
    child = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Child",
        slug="child",
        payload={"title": "Child", "body": "child body"},
        created_by="t",
    )
    cms.publish_node(parent.node_id, published_by="t")
    cms.publish_node(child.node_id, published_by="t")

    svc = _service(cms)
    overview = svc.overview()
    assert overview["metrics"]["node_count"] >= 2
    assert overview["metrics"]["edge_count"] >= 1

    backlinks = svc.backlinks("/cms/child")
    assert "/cms/parent" in backlinks["backlinks"]

    canvas = svc.canvas()
    assert canvas["node_count"] >= 2


# --- endpoints ------------------------------------------------------------


def test_graph_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        overview = client.get("/api/platform/graph/overview")
        assert overview.status_code == 200
        assert "metrics" in overview.json() and "orphans" in overview.json()

        canvas = client.get("/api/platform/graph/canvas")
        assert canvas.status_code == 200 and "nodes" in canvas.json()

        index = client.get("/api/platform/graph/backlinks-index")
        assert index.status_code == 200 and "items" in index.json()

        bl = client.get("/api/platform/graph/backlinks", params={"route": "/cms/demo"})
        assert bl.status_code == 200 and bl.json()["route_path"] == "/cms/demo"
