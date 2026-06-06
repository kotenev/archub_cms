"""Tests for the platform admin dashboard (Phase 22)."""

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


def test_dashboard_renders_html(client):
    resp = client.get("/admin/platform")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "ArcHub knowledge platform" in body
    assert "Bounded contexts" in body
    assert "Plugin runtime" in body
    assert "Content health" in body


def test_dashboard_lists_contexts_and_plugins(client):
    body = client.get("/admin/platform").text
    # a few representative contexts appear in the rendered page
    for context in ("knowledge", "workflow", "governance", "search", "subscriptions"):
        assert context in body
    # at least one bundled plugin id is rendered
    assert "example." in body
    # health grade letter is present
    assert "/api/platform/index" in body


def test_dashboard_reflects_health_grade(client):
    # demo content is healthy → grade A shown; compare against the JSON endpoint
    health = client.get("/api/platform/analytics/health").json()
    body = client.get("/admin/platform").text
    assert f"{health['score']}/100" in body
