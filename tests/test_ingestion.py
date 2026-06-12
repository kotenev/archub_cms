"""Tests for bulk markdown ingestion (Phase 22)."""

from __future__ import annotations

import pytest

from archub_cms.application.content_service import get_archub_content_service
from archub_cms.application.ingestion_service import get_archub_ingestion_service
from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.extensibility.host import PluginHost
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service

VAULT = [
    {
        "path": "notes/intro.md",
        "content": "---\ntitle: Intro\ntags: [kb, start]\n---\n# Intro\nWelcome.",
    },
    {"path": "notes/api.md", "content": "# API Guide\nHow to call the API."},
]


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def ingestion(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    host = PluginHost().load()
    content = get_archub_content_service(cms=cms)
    service = get_archub_ingestion_service(content=content, plugin_host=host)
    return cms, host, service


def test_import_vault_creates_and_publishes(ingestion):
    cms, host, service = ingestion
    fired: list[dict] = []
    get_event_bus().subscribe("ingestion.completed", lambda e: fired.append(e.metadata))

    result = service.import_markdown(VAULT, publish=True, actor="migrator")
    assert result["documents"] == 2
    assert result["created_count"] == 2
    assert result["failed"] == []
    routes = {c["route_path"] for c in result["created"]}
    assert "/cms/intro" in routes and "/cms/api-guide" in routes
    assert fired and fired[0]["created"] == 2

    # imported docs are published and searchable
    kb = get_archub_knowledge_base_service(cms, plugin_host=host)
    assert kb.documents()["total"] == 2
    hits = kb.hybrid_search("API", limit=5)
    assert hits and hits[0].route_path == "/cms/api-guide"


def test_import_single_markdown_string(ingestion):
    _, _, service = ingestion
    result = service.import_markdown("# Solo\nbody text", actor="m")
    assert result["created_count"] == 1
    assert result["created"][0]["route_path"] == "/cms/solo"


def test_failures_are_collected_not_raised(ingestion):
    _, _, service = ingestion
    # an unknown content type makes every create fail, but the batch completes
    result = service.import_markdown(VAULT, content_type_alias="does_not_exist", actor="m")
    assert result["created_count"] == 0
    assert len(result["failed"]) == 2
    assert all("error" in f for f in result["failed"])


def test_unknown_importer_raises(ingestion):
    _, _, service = ingestion
    with pytest.raises(ValueError):
        service.import_markdown("x", importer="nope")


# --- endpoint -------------------------------------------------------------


def test_ingestion_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        res = client.post(
            "/api/platform/ingest/markdown",
            json={"source": VAULT, "publish": True, "actor": "migrator"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["created_count"] == 2

        # the imported content is now discoverable via federated search
        search = client.get("/api/platform/search", params={"q": "API"}).json()
        assert any(i["route_path"] == "/cms/api-guide" for i in search["items"])

        bad = client.post("/api/platform/ingest/markdown", json={"source": "x", "importer": "nope"})
        assert bad.status_code == 422
