"""Tests for the packaging bounded context (Phase 11)."""

from __future__ import annotations

import pytest

from archub_cms.application.packaging_service import get_archub_packaging_service
from archub_cms.demo import seed_demo_content
from archub_cms.domain.packaging.package import (
    PACKAGE_SCHEMA_VERSION,
    ContentPackage,
    PackageInspection,
)
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


# --- domain ---------------------------------------------------------------


def test_content_package_schema_and_summary():
    supported = ContentPackage({"schema_version": PACKAGE_SCHEMA_VERSION})
    assert supported.is_supported and supported.is_empty
    assert not ContentPackage({"schema_version": "old"}).is_supported

    pkg = ContentPackage(
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "name": "P",
            "content": {"nodes": [{"a": 1}, {"b": 2}]},
            "content_model": {"content_types": [{}]},
            "redirects": [{}],
        }
    )
    summary = pkg.summary()
    assert summary["nodes"] == 2 and summary["content_types"] == 1 and summary["redirects"] == 1
    assert not pkg.is_empty


def test_package_inspection_from_result():
    insp = PackageInspection.from_result(
        {"ok": False, "issues": [{"severity": "error", "message": "x"}], "counts": {"nodes": 0}}
    )
    assert not insp.ok and insp.error_count == 1


# --- application service: full roundtrip ----------------------------------


def test_export_inspect_plan_import_roundtrip(cms):
    fired: list[str] = []
    get_event_bus().subscribe("packaging.exported", lambda e: fired.append("exported"))
    get_event_bus().subscribe("packaging.imported", lambda e: fired.append("imported"))

    svc = get_archub_packaging_service(cms=cms)
    package = svc.export(name="Demo Export", actor="admin")
    assert package.is_supported
    assert package.summary()["nodes"] >= 1

    inspection = svc.inspect(package.data)
    assert inspection.ok and inspection.error_count == 0

    plan = svc.plan(package.data)
    assert "actions" in plan and "inspection" in plan

    result = svc.import_package(package.data, actor="admin", overwrite=True)
    assert isinstance(result, dict)
    assert fired == ["exported", "imported"]


def test_import_rejects_unsupported_schema(cms):
    svc = get_archub_packaging_service(cms=cms)
    with pytest.raises(ValueError):
        svc.import_package({"schema_version": "bogus"}, actor="a")


# --- endpoints ------------------------------------------------------------


def test_packaging_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        exported = client.post("/api/platform/packaging/export", json={"name": "Bundle"})
        assert exported.status_code == 200
        package = exported.json()["package"]
        assert exported.json()["summary"]["is_supported"]

        inspect = client.post("/api/platform/packaging/inspect", json={"package": package})
        assert inspect.status_code == 200 and inspect.json()["ok"]

        plan = client.post("/api/platform/packaging/plan", json={"package": package})
        assert plan.status_code == 200 and "actions" in plan.json()

        imported = client.post(
            "/api/platform/packaging/import",
            json={"package": package, "actor": "admin", "overwrite": True},
        )
        assert imported.status_code == 200

        bad = client.post(
            "/api/platform/packaging/import", json={"package": {"schema_version": "nope"}}
        )
        assert bad.status_code == 422
