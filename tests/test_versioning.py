"""Tests for the versioning bounded context + diff (Phase 6)."""

from __future__ import annotations

import pytest

from archub_cms.application.versioning_service import (
    VersioningCommandService,
    VersionNotFoundError,
    get_archub_versioning_query_service,
)
from archub_cms.domain.versioning.diff import ChangeType, VersionDiff
from archub_cms.domain.versioning.version import Version
from archub_cms.infrastructure.sqlite.versioning_repository import CmsVersioningRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def node(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Doc",
        slug="doc",
        payload={"title": "Doc", "body": "v1"},
        created_by="t",
    )
    cms.update_node(
        created.node_id,
        name="Doc",
        slug="doc",
        payload={"title": "Doc 2", "body": "v2"},
        updated_by="t",
    )
    cms.publish_node(created.node_id, published_by="t")
    return cms, created.node_id


# --- domain: diff ---------------------------------------------------------


def test_version_diff_classifies_changes():
    v1 = Version(1, "n", 1, "draft", {"title": "A", "body": "x", "old": "gone"})
    v2 = Version(2, "n", 2, "draft", {"title": "B", "body": "x", "new": "here"})
    diff = VersionDiff.between(v1, v2)
    by_field = {c.field: c for c in diff.changes}
    assert by_field["title"].change is ChangeType.CHANGED
    assert by_field["title"].before == "A" and by_field["title"].after == "B"
    assert by_field["old"].change is ChangeType.REMOVED
    assert by_field["new"].change is ChangeType.ADDED
    assert "body" not in by_field  # unchanged
    assert diff.summary() == {"added": 1, "removed": 1, "changed": 1}
    assert not diff.is_empty


def test_identical_versions_have_empty_diff():
    v = Version(1, "n", 1, "draft", {"title": "Same"})
    assert VersionDiff.between(v, v).is_empty


# --- repository + query service ------------------------------------------


def test_history_and_repository(node):
    cms, node_id = node
    repo = CmsVersioningRepository(cms)
    versions = repo.history(node_id)
    assert versions and all(isinstance(v, Version) for v in versions)
    assert repo.get(node_id, versions[-1].version_no) is not None
    assert repo.get(node_id, 9999) is None


def test_query_diff_between_versions(node):
    cms, node_id = node
    q = get_archub_versioning_query_service(cms=cms)
    nos = sorted(v["version_no"] for v in q.history(node_id)["items"])
    diff = q.diff(node_id, from_version_no=nos[0], to_version_no=nos[1])
    fields = {c["field"]: c for c in diff["changes"]}
    assert fields["title"]["after"] == "Doc 2"
    assert fields["body"]["before"] == "v1" and fields["body"]["after"] == "v2"


def test_diff_missing_version_raises(node):
    cms, node_id = node
    q = get_archub_versioning_query_service(cms=cms)
    with pytest.raises(VersionNotFoundError):
        q.diff(node_id, from_version_no=1, to_version_no=9999)


# --- restore command ------------------------------------------------------


def test_restore_emits_event(node):
    cms, node_id = node
    fired: list[int] = []
    get_event_bus().subscribe(
        "content.version.restored", lambda e: fired.append(e.metadata["version_no"])
    )
    nos = sorted(v.version_no for v in CmsVersioningRepository(cms).history(node_id))
    result = VersioningCommandService(cms=cms).restore(node_id, nos[0], actor="tester")
    assert result["restored_version_no"] == nos[0]
    assert fired == [nos[0]]


def test_restore_missing_version_raises(node):
    cms, node_id = node
    with pytest.raises(VersionNotFoundError):
        VersioningCommandService(cms=cms).restore(node_id, 9999, actor="t")


# --- endpoints ------------------------------------------------------------


def test_versioning_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="P",
        slug="p",
        payload={"title": "P1", "body": "a"},
        created_by="t",
    )
    cms.update_node(
        created.node_id,
        name="P",
        slug="p",
        payload={"title": "P2", "body": "b"},
        updated_by="t",
    )
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        hist = client.get(f"/api/platform/versioning/{created.node_id}/history")
        assert hist.status_code == 200
        nos = sorted(v["version_no"] for v in hist.json()["items"])

        diff = client.get(
            f"/api/platform/versioning/{created.node_id}/diff",
            params={"from": nos[0], "to": nos[1]},
        )
        assert diff.status_code == 200
        assert diff.json()["summary"]["changed"] >= 1

        restored = client.post(
            f"/api/platform/versioning/{created.node_id}/restore",
            json={"version_no": nos[0], "actor": "tester"},
        )
        assert restored.status_code == 200
        assert restored.json()["restored_version_no"] == nos[0]

        missing = client.get(
            f"/api/platform/versioning/{created.node_id}/diff", params={"from": 1, "to": 9999}
        )
        assert missing.status_code == 404
