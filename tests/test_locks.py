"""Tests for the edit-locks context (Phase 28)."""

from __future__ import annotations

import pytest

from archub_cms.application.lock_service import (
    LockCommandService,
    LockConflictError,
    get_archub_lock_query_service,
)
from archub_cms.domain.locks.lock import EditLock
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
        payload={"title": "Doc"},
        created_by="ed",
    )
    return cms, created.node_id


# --- domain ---------------------------------------------------------------


def test_editlock_lifecycle_predicates():
    lock = EditLock("n", "alice", acquired_at=1000.0, expires_at=1100.0)
    assert lock.is_active(1050.0) and not lock.is_expired(1050.0)
    assert lock.is_expired(1200.0)
    assert lock.held_by("ALICE") and not lock.held_by("bob")
    assert lock.remaining_seconds(1070.0) == 30.0
    # blocks another editor while active, not after expiry, never the holder
    assert lock.blocks("bob", 1050.0)
    assert not lock.blocks("bob", 1200.0)
    assert not lock.blocks("alice", 1050.0)


# --- command + query ------------------------------------------------------


def test_acquire_emits_single_event_and_reports(node):
    cms, node_id = node
    fired: list[str] = []
    get_event_bus().subscribe("editlock.acquired", lambda e: fired.append(e.aggregate_id))
    cmd = LockCommandService(cms=cms)
    result = cmd.acquire(node_id, owner="alice", ttl_seconds=120, note="editing")
    assert result["owner"] == "alice" and result["active"] is True
    assert fired == [node_id]  # exactly one (no legacy collision)

    q = get_archub_lock_query_service(cms=cms)
    assert q.lock(node_id)["owner"] == "alice"
    assert q.active_locks()["total"] == 1


def test_conflict_and_force_acquire(node):
    cms, node_id = node
    cmd = LockCommandService(cms=cms)
    cmd.acquire(node_id, owner="alice")
    with pytest.raises(LockConflictError):
        cmd.acquire(node_id, owner="bob")
    # the same owner re-acquiring is fine (refreshes)
    cmd.acquire(node_id, owner="alice")
    # force lets bob take over
    cmd.acquire(node_id, owner="bob", force=True)
    assert get_archub_lock_query_service(cms=cms).lock(node_id)["owner"] == "bob"


def test_release_and_validation(node):
    cms, node_id = node
    cmd = LockCommandService(cms=cms)
    fired: list[str] = []
    get_event_bus().subscribe("editlock.released", lambda e: fired.append(e.aggregate_id))
    cmd.acquire(node_id, owner="alice")
    assert cmd.release(node_id, owner="alice")["released"] is True
    assert fired == [node_id]
    assert get_archub_lock_query_service(cms=cms).active_locks()["total"] == 0

    with pytest.raises(ValueError):
        cmd.acquire(node_id, owner="")


# --- endpoints ------------------------------------------------------------


def test_lock_endpoints(tmp_path, monkeypatch):
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
        payload={"title": "P"},
        created_by="ed",
    )
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        assert client.get(f"/api/platform/locks/{created.node_id}").json()["locked"] is False

        acquired = client.post(
            f"/api/platform/locks/{created.node_id}/acquire", json={"owner": "alice"}
        )
        assert acquired.status_code == 200 and acquired.json()["owner"] == "alice"

        # bob conflicts → 409
        conflict = client.post(
            f"/api/platform/locks/{created.node_id}/acquire", json={"owner": "bob"}
        )
        assert conflict.status_code == 409

        assert client.get("/api/platform/locks").json()["total"] == 1

        released = client.post(
            f"/api/platform/locks/{created.node_id}/release", json={"owner": "alice"}
        )
        assert released.status_code == 200 and released.json()["released"] is True
