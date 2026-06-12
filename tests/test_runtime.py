"""Tests for the runtime / RAG-export bounded context (Phase 13)."""

from __future__ import annotations

import pytest

from archub_cms.application.runtime_service import (
    RuntimeCommandService,
    get_archub_runtime_query_service,
)
from archub_cms.demo import seed_demo_content
from archub_cms.domain.runtime.models import ExportStatus, RagHit, RuntimeSnapshot
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


# --- domain read models ---------------------------------------------------


def test_runtime_snapshot_model():
    snap = RuntimeSnapshot.from_snapshot(
        {"generated_at": 5.0, "counts": {"ai_experts": 2, "rag_materials": 3}}
    )
    assert snap.total == 5
    assert snap.as_dict()["counts"]["rag_materials"] == 3


def test_export_status_model():
    st = ExportStatus.from_result(
        {"export_dir": "/x", "exists": True, "generated_at": 9.0, "needs_export": False}
    )
    assert st.exists and st.export_dir == "/x" and not st.needs_export


def test_rag_hit_model():
    hit = RagHit(route_path="/cms/m", title="M", corpus_key="demo", excerpt="text")
    assert hit.as_dict()["corpus_key"] == "demo"


# --- query + command services ---------------------------------------------


def test_snapshot_and_status_and_export(cms, tmp_path):
    export_dir = tmp_path / "runtime"
    q = get_archub_runtime_query_service(cms=cms)

    snap = q.snapshot()
    assert snap["counts"].get("rag_materials", 0) >= 1
    assert snap["total"] >= 1

    before = q.status(export_dir)
    assert before["exists"] is False and before["needs_export"] is True

    fired: list[str] = []
    get_event_bus().subscribe("runtime.export.completed", lambda e: fired.append("exported"))
    manifest = RuntimeCommandService(cms=cms).export(export_dir=export_dir, actor="admin")
    assert manifest["counts"]["rag_materials"] >= 1
    assert fired == ["exported"]  # exactly one domain event (no legacy collision)

    after = q.status(export_dir)
    assert after["exists"] is True


def test_rebuild_indexes_emits_event(cms, tmp_path):
    fired: list[str] = []
    get_event_bus().subscribe("runtime.index.rebuilt", lambda e: fired.append(e.aggregate_id))
    result = RuntimeCommandService(cms=cms).rebuild_indexes(
        corpus_key="demo", export_dir=tmp_path / "rt", actor="admin"
    )
    assert isinstance(result, dict)
    assert fired == ["demo"]


def test_rag_search(cms):
    q = get_archub_runtime_query_service(cms=cms)
    result = q.search("demo", "ArcHub", limit=5)
    assert result["corpus_key"] == "demo"
    assert result["total"] >= 1
    assert result["items"][0]["route_path"].startswith("/cms")


# --- endpoints ------------------------------------------------------------


def test_runtime_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("ARCHUB_RUNTIME_EXPORT_DIR", str(tmp_path / "export"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        snap = client.get("/api/platform/runtime/snapshot")
        assert snap.status_code == 200 and "counts" in snap.json()

        status_before = client.get("/api/platform/runtime/status").json()
        assert status_before["exists"] is False

        exported = client.post("/api/platform/runtime/export", json={"actor": "admin"})
        assert exported.status_code == 200 and "counts" in exported.json()

        status_after = client.get("/api/platform/runtime/status").json()
        assert status_after["exists"] is True

        search = client.get(
            "/api/platform/runtime/search", params={"corpus": "demo", "q": "ArcHub"}
        )
        assert search.status_code == 200 and search.json()["total"] >= 1
