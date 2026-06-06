"""Tests for the self-describing platform API index (Phase 21)."""

from __future__ import annotations

import pytest

from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)
    with TestClient(create_archub_app()) as test_client:
        yield test_client


def test_index_groups_routes_by_context(client):
    body = client.get("/api/platform/index").json()
    sections = body["sections"]
    # major contexts are all discoverable as sections
    for section in (
        "knowledge",
        "modeling",
        "delivery",
        "versioning",
        "governance",
        "workflow",
        "media",
        "packaging",
        "graph",
        "runtime",
        "localization",
        "analytics",
        "webhooks",
        "search",
        "subscriptions",
        "plugins",
    ):
        assert section in sections, f"missing section: {section}"
    assert body["section_count"] >= 16
    assert body["route_count"] >= 50


def test_index_entries_have_paths_and_methods(client):
    sections = client.get("/api/platform/index").json()["sections"]
    workflow = sections["workflow"]
    assert all(entry["path"].startswith("/api/platform/") for entry in workflow)
    # the transition route is a POST
    transition = [e for e in workflow if e["path"].endswith("/transition")]
    assert transition and "POST" in transition[0]["methods"]
    # HEAD/OPTIONS are filtered out
    for entry in workflow:
        assert "HEAD" not in entry["methods"]


def test_index_is_self_inclusive(client):
    sections = client.get("/api/platform/index").json()["sections"]
    paths = {e["path"] for routes in sections.values() for e in routes}
    assert "/api/platform/index" in paths
    assert "/api/platform/capabilities" in paths


def test_capabilities_and_index_consistent(client):
    caps = client.get("/api/platform/capabilities").json()
    index = client.get("/api/platform/index").json()
    # capabilities lists the bounded contexts; the API index exposes at least that many sections
    assert caps["context_count"] == 18
    assert index["section_count"] >= caps["context_count"]
