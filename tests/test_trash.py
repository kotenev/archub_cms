"""Tests for the trash / recycle-bin context (Phase 27)."""

from __future__ import annotations

import pytest

from archub_cms.application.trash_service import (
    TrashCommandService,
    TrashItemNotFoundError,
    get_archub_trash_query_service,
)
from archub_cms.domain.trash.item import TrashedItem
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


def _make(cms, name: str, slug: str):
    return cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name=name,
        slug=slug,
        payload={"title": name},
        created_by="ed",
    )


# --- domain ---------------------------------------------------------------


def test_trashed_item_from_payload():
    item = TrashedItem.from_payload(
        {"node_id": "n", "name": "Doc", "route_path": "/cms/doc", "trashed_at": 5.0}
    )
    assert item.node_id == "n" and item.original_route_path == "/cms/doc"
    assert item.as_dict()["original_route_path"] == "/cms/doc"


# --- list / restore / purge / empty --------------------------------------


def test_delete_lists_in_trash_then_restore(cms):
    node = _make(cms, "Doomed", "doomed")
    cms.publish_node(node.node_id, published_by="ed")
    cms.delete_node(node.node_id, deleted_by="ed")

    q = get_archub_trash_query_service(cms=cms)
    assert q.items()["total"] == 1
    assert q.items()["items"][0]["name"] == "Doomed"

    fired: list[str] = []
    get_event_bus().subscribe("trash.item.restored", lambda e: fired.append(e.aggregate_id))
    result = TrashCommandService(cms=cms).restore(node.node_id, actor="admin")
    assert result["route_path"] == "/cms/doomed"
    assert fired == [node.node_id]  # exactly one (no legacy collision)
    assert q.items()["total"] == 0


def test_purge_removes_permanently(cms):
    node = _make(cms, "Junk", "junk")
    cms.delete_node(node.node_id, deleted_by="ed")
    fired: list[str] = []
    get_event_bus().subscribe("trash.item.purged", lambda e: fired.append(e.aggregate_id))

    cmd = TrashCommandService(cms=cms)
    assert cmd.purge(node.node_id, actor="admin")["purged"] is True
    assert fired == [node.node_id]
    assert get_archub_trash_query_service(cms=cms).items()["total"] == 0
    assert cms.get_node(node.node_id) is None


def test_restore_or_purge_non_trashed_raises(cms):
    node = _make(cms, "Live", "live")  # never deleted
    cmd = TrashCommandService(cms=cms)
    with pytest.raises(TrashItemNotFoundError):
        cmd.restore(node.node_id, actor="x")
    with pytest.raises(TrashItemNotFoundError):
        cmd.purge(node.node_id, actor="x")


def test_empty_bin(cms):
    for i in range(3):
        node = _make(cms, f"Trash{i}", f"trash-{i}")
        cms.delete_node(node.node_id, deleted_by="ed")
    fired: list[int] = []
    get_event_bus().subscribe("trash.emptied", lambda e: fired.append(e.metadata["purged"]))

    result = TrashCommandService(cms=cms).empty(actor="admin")
    assert result["purged_count"] == 3
    assert fired == [3]
    assert get_archub_trash_query_service(cms=cms).items()["total"] == 0


# --- endpoints ------------------------------------------------------------


def test_trash_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    a = _make(cms, "Restorable", "restorable")
    b = _make(cms, "Removable", "removable")
    cms.delete_node(a.node_id, deleted_by="ed")
    cms.delete_node(b.node_id, deleted_by="ed")
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        assert client.get("/api/platform/trash").json()["total"] == 2

        restored = client.post(f"/api/platform/trash/{a.node_id}/restore", json={"actor": "admin"})
        assert restored.status_code == 200 and restored.json()["route_path"] == "/cms/restorable"

        purged = client.delete(f"/api/platform/trash/{b.node_id}", params={"actor": "admin"})
        assert purged.status_code == 200 and purged.json()["purged"] is True

        assert client.get("/api/platform/trash").json()["total"] == 0
        assert client.post(f"/api/platform/trash/{a.node_id}/restore", json={}).status_code == 404
