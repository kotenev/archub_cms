"""Tests for the delivery (syndication) bounded context (Phase 5)."""

from __future__ import annotations

import pytest

from archub_cms.application.delivery_read_service import (
    RedirectCommandService,
    get_archub_delivery_read_service,
)
from archub_cms.demo import seed_demo_content
from archub_cms.domain.delivery.redirect import Redirect, normalize_path
from archub_cms.infrastructure.sqlite.delivery_repository import CmsDeliveryRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
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


# --- domain: Redirect aggregate ------------------------------------------


def test_normalize_path():
    assert normalize_path("cms/docs/") == "/cms/docs"
    assert normalize_path("/") == "/cms"
    assert normalize_path("") == "/cms"


def test_redirect_matching_and_validation():
    r = Redirect(redirect_id="r1", source_path="/cms/old", target_path="/cms/new", status_code=301)
    assert r.is_permanent
    assert r.matches("/cms/old/") and r.matches("cms/old")
    assert not r.matches("/cms/other")
    assert r.valid

    bad = Redirect(redirect_id="r2", source_path="/cms/x", target_path="/cms/x", status_code=999)
    errors = bad.validate()
    assert any("differ" in e for e in errors)
    assert any("status code" in e for e in errors)


# --- repository + read service -------------------------------------------


def test_read_service_syndication(cms):
    svc = get_archub_delivery_read_service(cms=cms)
    assert svc.sitemap()["total"] >= 1
    assert svc.feed(limit=10)["total"] >= 1
    tags = svc.tags()
    assert tags["total"] >= 1
    # by_tag should return demo content tagged "demo"
    assert "items" in svc.by_tag("demo")


def test_repository_returns_domain_redirects(cms):
    cms.upsert_redirect(source_path="/cms/a", target_path="/cms/b", updated_by="t")
    repo = CmsDeliveryRepository(cms)
    redirects = repo.list_redirects()
    assert redirects and all(isinstance(r, Redirect) for r in redirects)
    assert repo.resolve_redirect("/cms/a") is not None


# --- redirect command service --------------------------------------------


def test_redirect_command_emits_event_and_resolves(cms):
    fired: list[str] = []
    get_event_bus().subscribe("delivery.redirect.upserted", lambda e: fired.append(e.aggregate_id))

    cmd = RedirectCommandService(cms=cms)
    redirect = cmd.upsert_redirect(
        source_path="/cms/old-docs", target_path="/cms/developers", actor="tester"
    )
    assert redirect.redirect_id and fired == [redirect.redirect_id]

    svc = get_archub_delivery_read_service(cms=cms)
    resolved = svc.resolve("/cms/old-docs")
    assert resolved is not None and resolved["target_path"] == "/cms/developers"


def test_redirect_command_rejects_invalid(cms):
    cmd = RedirectCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.upsert_redirect(source_path="/cms/x", target_path="/cms/x", actor="t")


# --- endpoints ------------------------------------------------------------


def test_delivery_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        assert client.get("/api/platform/delivery/sitemap").json()["total"] >= 1
        assert client.get("/api/platform/delivery/feed").json()["total"] >= 1
        assert client.get("/api/platform/delivery/tags").status_code == 200

        # no redirect yet → 404
        assert (
            client.get("/api/platform/delivery/resolve", params={"path": "/cms/nope"}).status_code
            == 404
        )
