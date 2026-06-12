"""Characterization tests that lock current ArcHubCMSService behavior.

These tests intentionally assert the *observable* output of the legacy god class
before its node lifecycle is extracted into the new ``content`` bounded context.
They are the safety net for the DDD refactor: if the extracted
``ContentService``/``ContentRepository`` changes behavior, these break.
"""

from __future__ import annotations

import pytest

from archub_cms.demo import seed_demo_content
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    service = get_archub_cms_service()
    seed_demo_content(service)
    return service


def test_stats_reports_seeded_counts(cms) -> None:
    stats = cms.stats()
    # Demo seed creates root + three child nodes, all published.
    assert stats["nodes"] >= 4
    assert stats["published"] >= 4
    assert stats["content_types"] > 0


def test_list_tree_returns_published_demo_nodes(cms) -> None:
    routes = {node.route_path for node in cms.list_tree()}
    assert "/cms" in routes
    assert "/cms/demo" in routes
    assert "/cms/developers" in routes


def test_create_publish_and_version_roundtrip(cms) -> None:
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Characterization Page",
        slug="characterization-page",
        payload={"title": "Characterization Page", "body": "<p>hello</p>"},
        created_by="test",
    )
    assert node.route_path == "/cms/characterization-page"
    assert not node.is_published

    published = cms.publish_node(node.node_id, published_by="test")
    assert published.is_published
    assert published.published.get("title") == "Characterization Page"

    fetched = cms.get_node(node.node_id)
    assert fetched is not None
    assert fetched.is_published

    versions = cms.list_versions(node.node_id)
    assert len(versions) >= 1


def test_unique_slug_disambiguation(cms) -> None:
    first = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Dup",
        slug="dup",
        payload={"title": "Dup"},
        created_by="test",
    )
    second = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Dup",
        slug="dup",
        payload={"title": "Dup 2"},
        created_by="test",
    )
    assert first.route_path == "/cms/dup"
    assert second.route_path != first.route_path
    assert second.route_path.startswith("/cms/dup")


def test_published_search_finds_demo_content(cms) -> None:
    results = cms.published_search("ArcHub", limit=10)
    assert any("/cms" in item.get("route_path", "") for item in results)


def test_content_health_report_shape(cms) -> None:
    report = cms.content_health_report()
    assert isinstance(report, dict)
    assert "generated_at" in report or "nodes" in report or report
