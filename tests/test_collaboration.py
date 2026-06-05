"""Tests for the collaboration bounded context (Phase 2)."""

from __future__ import annotations

import pytest

from archub_cms.application.collaboration_service import (
    CommentNotFoundError,
    get_archub_collaboration_service,
)
from archub_cms.domain.collaboration.comment import Comment, ReactionKind
from archub_cms.domain.collaboration.events import (
    COMMENT_CREATED,
    MENTION_CREATED,
    REACTION_ADDED,
)
from archub_cms.domain.collaboration.value_objects import Mention, extract_mentions
from archub_cms.extensibility.host import PluginHost
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    return get_archub_collaboration_service(db_path=cms.db_path)


# --- domain ---------------------------------------------------------------


def test_extract_mentions_dedupes_and_normalizes():
    mentions = extract_mentions("hi @Bob and @bob, cc @Carol-1")
    assert mentions == (Mention("bob"), Mention("carol-1"))


def test_comment_reactions_and_resolve():
    c = Comment(comment_id="c1", node_id="n1", author="alice", body="hello @bob")
    assert c.mentions == (Mention("bob"),)
    assert c.add_reaction("BOB", ReactionKind.LIKE) is True
    assert c.add_reaction("bob", "like") is False  # idempotent, case-insensitive
    assert c.reaction_counts() == {"like": 1}
    assert c.resolve().ok
    assert not c.resolve().ok  # already resolved


def test_comment_validation():
    assert not Comment(comment_id="c", node_id="n", author="a", body="   ").validate().ok
    assert not Comment(comment_id="c", node_id="n", author=" ", body="hi").validate().ok


# --- application service + events ----------------------------------------


def test_add_comment_emits_events(service):
    fired: list[str] = []
    bus = get_event_bus()
    bus.subscribe(COMMENT_CREATED, lambda e: fired.append(e.event_type))
    bus.subscribe(MENTION_CREATED, lambda e: fired.append(e.metadata.get("mentioned")))

    comment = service.add_comment(node_id="root", author="alice", body="ping @bob @carol")
    assert comment.comment_id
    assert COMMENT_CREATED in fired
    assert "bob" in fired and "carol" in fired


def test_threading_reactions_and_resolve(service):
    root = service.add_comment(node_id="root", author="alice", body="parent")
    service.add_comment(
        node_id="root", author="bob", body="child", parent_comment_id=root.comment_id
    )
    service.react(root.comment_id, user="carol", kind="celebrate")
    service.resolve_comment(root.comment_id, actor="alice")

    thread = service.thread_for_node("root")
    assert thread["total"] == 2
    assert len(thread["items"]) == 1  # one root
    assert len(thread["items"][0]["replies"]) == 1
    assert thread["items"][0]["reactions"] == {"celebrate": 1}
    assert thread["items"][0]["resolved"] is True


def test_include_resolved_filter_and_mentions_query(service):
    a = service.add_comment(node_id="root", author="alice", body="open @dave")
    b = service.add_comment(node_id="root", author="bob", body="to close")
    service.resolve_comment(b.comment_id, actor="bob")

    open_only = service.thread_for_node("root", include_resolved=False)
    assert open_only["total"] == 1
    assert open_only["items"][0]["comment_id"] == a.comment_id

    mentions = service.mentions_for_user("dave")
    assert mentions["total"] == 1


def test_delete_and_missing(service):
    c = service.add_comment(node_id="root", author="alice", body="bye")
    assert service.delete_comment(c.comment_id, actor="alice") is True
    assert service.delete_comment("nope", actor="alice") is False
    with pytest.raises(CommentNotFoundError):
        service.resolve_comment("nope", actor="alice")


def test_reaction_added_event(service):
    seen: list[str] = []
    get_event_bus().subscribe(REACTION_ADDED, lambda e: seen.append(e.metadata.get("kind")))
    c = service.add_comment(node_id="root", author="alice", body="x")
    service.react(c.comment_id, user="bob", kind="thanks")
    assert seen == ["thanks"]


# --- plugin reacts to collaboration events -------------------------------


def test_notifications_plugin_records_mentions(service):
    host = PluginHost().load()
    assert "example.notifications" in {p["plugin_id"] for p in host.report()["loaded"]}

    service.add_comment(node_id="root", author="alice", body="review please @bob")

    plugin = host.plugin_instance("example.notifications")
    feed = plugin.notifications_for("bob")
    assert len(feed) == 1
    assert feed[0]["type"] == MENTION_CREATED
    assert feed[0]["actor"] == "alice"


# --- web endpoints --------------------------------------------------------


def test_collaboration_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        created = client.post(
            "/api/platform/collaboration/nodes/root/comments",
            json={"author": "alice", "body": "hello @bob"},
        )
        assert created.status_code == 200
        comment_id = created.json()["comment_id"]

        react = client.post(
            f"/api/platform/collaboration/comments/{comment_id}/reactions",
            json={"user": "carol", "kind": "like"},
        )
        assert react.status_code == 200
        assert react.json()["reactions"] == {"like": 1}

        listing = client.get("/api/platform/collaboration/nodes/root/comments")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        notif = client.get("/api/platform/collaboration/notifications/bob")
        assert notif.status_code == 200
        assert notif.json()["total"] >= 1
