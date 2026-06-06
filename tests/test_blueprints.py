"""Tests for the blueprints/templates context (Phase 26)."""

from __future__ import annotations

import pytest

from archub_cms.application.blueprint_service import (
    BlueprintCommandService,
    BlueprintNotFoundError,
    get_archub_blueprint_query_service,
)
from archub_cms.domain.blueprints.blueprint import Blueprint
from archub_cms.infrastructure.sqlite.blueprint_repository import CmsBlueprintRepository
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


def test_blueprint_merge_overrides_and_validation():
    bp = Blueprint(
        "b", "page", "Meeting", payload={"title": "Meeting", "body": "Agenda", "tags": "m"}
    )
    merged = bp.merge_overrides({"title": "Sprint Review"})
    assert merged == {"title": "Sprint Review", "body": "Agenda", "tags": "m"}  # override + keep
    assert bp.field_names() == ("body", "tags", "title")
    assert bp.valid
    assert not Blueprint("b", "", "", payload={}).valid


# --- command + query ------------------------------------------------------


def test_create_blueprint_emits_event_and_lists(cms):
    fired: list[str] = []
    get_event_bus().subscribe("blueprint.upserted", lambda e: fired.append(e.aggregate_id))
    cmd = BlueprintCommandService(cms=cms)
    bp = cmd.create_blueprint(
        content_type_alias="page",
        name="Meeting Notes",
        payload={"title": "Meeting", "body": "<p>Agenda</p>"},
        actor="admin",
    )
    assert bp.blueprint_id and fired == [bp.blueprint_id]

    q = get_archub_blueprint_query_service(cms=cms)
    assert q.blueprints()["total"] == 1
    assert q.blueprint(bp.blueprint_id)["name"] == "Meeting Notes"
    assert CmsBlueprintRepository(cms).get(bp.blueprint_id) is not None


def test_instantiate_merges_template_with_overrides(cms):
    fired: list[str] = []
    get_event_bus().subscribe(
        "content.instantiated_from_blueprint", lambda e: fired.append(e.metadata["blueprint_id"])
    )
    cmd = BlueprintCommandService(cms=cms)
    bp = cmd.create_blueprint(
        content_type_alias="page",
        name="Tpl",
        payload={"title": "Template Title", "body": "<p>Boilerplate</p>"},
        actor="admin",
    )
    result = cmd.instantiate(
        bp.blueprint_id,
        parent_id="root",
        name="Q3 Review",
        overrides={"title": "Q3 Review"},
        actor="ed",
    )
    assert result["route_path"] == "/cms/q3-review"
    assert fired == [bp.blueprint_id]

    node = cms.get_node(result["node_id"])
    assert node.draft.get("title") == "Q3 Review"  # overridden
    assert "Boilerplate" in str(node.draft.get("body"))  # template field kept


def test_instantiate_missing_blueprint_raises(cms):
    with pytest.raises(BlueprintNotFoundError):
        BlueprintCommandService(cms=cms).instantiate("nope", name="x", actor="e")


def test_create_blueprint_validation(cms):
    with pytest.raises(ValueError):
        BlueprintCommandService(cms=cms).create_blueprint(
            content_type_alias="", name="", payload={}, actor="a"
        )


# --- endpoints ------------------------------------------------------------


def test_blueprint_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        created = client.post(
            "/api/platform/blueprints",
            json={
                "content_type_alias": "page",
                "name": "Runbook Template",
                "payload": {"title": "Runbook", "body": "## Steps"},
                "actor": "admin",
            },
        )
        assert created.status_code == 200
        bp_id = created.json()["blueprint_id"]

        assert client.get("/api/platform/blueprints").json()["total"] >= 1
        assert client.get(f"/api/platform/blueprints/{bp_id}").json()["name"] == "Runbook Template"

        inst = client.post(
            f"/api/platform/blueprints/{bp_id}/instantiate",
            json={"name": "DB Runbook", "overrides": {"title": "DB Runbook"}, "actor": "ed"},
        )
        assert inst.status_code == 200
        assert inst.json()["route_path"] == "/cms/db-runbook"

        assert client.get("/api/platform/blueprints/missing").status_code == 404
        bad = client.post("/api/platform/blueprints/missing/instantiate", json={"name": "x"})
        assert bad.status_code == 404
