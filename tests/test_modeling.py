"""Tests for the modeling bounded context (Phase 4)."""

from __future__ import annotations

import pytest

from archub_cms.application.modeling_service import (
    ModelingCommandService,
    get_archub_modeling_query_service,
)
from archub_cms.domain.modeling.content_type import ContentTypeModel
from archub_cms.domain.modeling.field import Field
from archub_cms.infrastructure.sqlite.modeling_repository import CmsModelingRepository
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
    return get_archub_cms_service()


# --- domain ---------------------------------------------------------------


def test_field_validation():
    assert Field(alias="title", name="Title").valid
    assert not Field(alias="1bad", name="X").valid
    assert not Field(alias="ok", name="  ").valid


def test_content_type_invariants():
    good = ContentTypeModel(alias="page", name="Page", fields=(Field(alias="body", name="Body"),))
    assert good.valid
    assert good.field("body") is not None
    bad = ContentTypeModel(alias="1x", name="", is_element=True, allow_at_root=True)
    errors = bad.validate()
    assert any("alias" in e for e in errors)
    assert any("name is required" in e for e in errors)
    assert any("element" in e for e in errors)


def test_content_type_composition_and_child_helpers():
    ct = ContentTypeModel(
        alias="article",
        name="Article",
        composition_aliases=("seo",),
        allowed_child_aliases=("comment",),
    )
    assert ct.is_composed
    assert ct.allows_child("comment")
    assert not ct.allows_child("page")


# --- repository + query service -------------------------------------------


def test_repository_maps_hydrated_reads(cms):
    repo = CmsModelingRepository(cms)
    types = repo.list_content_types()
    assert types and all(isinstance(t, ContentTypeModel) for t in types)
    page = repo.get_content_type("page")
    assert page is not None and page.alias == "page"
    assert repo.list_data_types() and repo.list_templates()


def test_query_service_report(cms):
    q = get_archub_modeling_query_service(cms=cms)
    report = q.report()
    assert report["content_type_total"] >= 1
    assert report["data_type_total"] >= 1
    assert "page" in [ct["alias"] for ct in q.content_types()["items"]]


# --- command service ------------------------------------------------------


def test_command_upsert_emits_event_and_persists(cms):
    fired: list[str] = []
    get_event_bus().subscribe("content_model.type.upserted", lambda e: fired.append(e.aggregate_id))

    cmd = ModelingCommandService(cms=cms)
    model = cmd.upsert_content_type(
        alias="faq_item",
        name="FAQ Item",
        fields=[{"alias": "question", "name": "Question", "required": True}],
        allow_at_root=True,
        actor="tester",
    )
    assert model.alias == "faq_item"
    assert fired == ["faq_item"]
    # persisted and visible through the query side
    assert get_archub_modeling_query_service(cms=cms).content_type("faq_item") is not None


def test_command_rejects_invalid_model(cms):
    cmd = ModelingCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.upsert_content_type(alias="1bad", name="", actor="t")


# --- endpoints ------------------------------------------------------------


def test_modeling_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        report = client.get("/api/platform/modeling/report")
        assert report.status_code == 200
        assert report.json()["content_type_total"] >= 1

        types = client.get("/api/platform/modeling/content-types").json()
        assert types["total"] >= 1

        page = client.get("/api/platform/modeling/content-types/page")
        assert page.status_code == 200
        assert page.json()["alias"] == "page"

        missing = client.get("/api/platform/modeling/content-types/does-not-exist")
        assert missing.status_code == 404

        assert client.get("/api/platform/modeling/data-types").json()["total"] >= 1
