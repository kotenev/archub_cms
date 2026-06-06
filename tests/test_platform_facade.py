"""Tests for the ArcHubPlatform composition root / facade (Phase 18)."""

from __future__ import annotations

import pytest

from archub_cms.application.platform import ArcHubPlatform, get_archub_platform
from archub_cms.demo import seed_demo_content
from archub_cms.extensibility.host import PluginHost
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def platform(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    seed_demo_content(cms)
    host = PluginHost().load()
    return ArcHubPlatform(cms=cms, plugin_host=host)


# --- wiring ---------------------------------------------------------------


def test_all_context_services_resolve(platform):
    for name in (
        "content",
        "knowledge",
        "collaboration",
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
        assert getattr(platform, name) is not None


def test_shared_infrastructure(platform):
    # one CMS, one event bus, one knowledge instance reused downstream
    assert platform.content._cms is platform.cms
    assert platform.event_bus is platform.content._bus
    assert platform.graph._knowledge is platform.knowledge
    assert platform.search._knowledge is platform.knowledge


def test_cached_property_returns_same_instance(platform):
    assert platform.modeling is platform.modeling
    assert platform.knowledge is platform.knowledge


def test_facade_delegates_to_contexts(platform):
    assert platform.modeling.content_types()["total"] >= 1
    assert platform.analytics.health()["grade"] in {"A", "B", "C", "D", "F"}
    assert platform.delivery.sitemap()["total"] >= 1


# --- capabilities self-description ---------------------------------------


def test_capabilities_surface(platform):
    caps = platform.capabilities()
    assert caps["context_count"] == 17
    assert len(caps["bounded_contexts"]) == 17
    assert "Composition Root (this facade)" in caps["architectural_patterns"]
    ext = caps["plugins"]["extension_points"]
    # auth, storage and notification channels are all wired
    assert ext["auth_providers"] >= 1
    assert ext["storage_backends"] >= 1
    assert ext["notification_channels"] >= 1
    assert caps["plugins"]["loaded"] >= 9
    assert "offline_default" in caps["llm"]


def test_factory_binds_to_given_cms(platform):
    built = get_archub_platform(cms=platform.cms, plugin_host=platform.plugin_host)
    assert built.cms is platform.cms


# --- endpoint -------------------------------------------------------------


def test_capabilities_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        caps = client.get("/api/platform/capabilities")
        assert caps.status_code == 200
        body = caps.json()
        assert body["context_count"] == 17
        assert body["plugins"]["loaded"] >= 9
        assert body["product"].startswith("ArcHub")
