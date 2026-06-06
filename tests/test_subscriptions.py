"""Tests for the subscriptions/watchers context (Phase 20)."""

from __future__ import annotations

import pytest

from archub_cms.application.subscription_service import (
    SubscriptionCommandService,
    get_archub_subscription_query_service,
)
from archub_cms.domain.subscriptions.subscription import Subscription
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.subscription_repository import SqliteSubscriptionRepository
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


def test_subscription_matching():
    s = Subscription("s", "bob", node_id="n1", event_prefix="content.")
    assert s.matches(action="content.published", node_id="n1")
    assert not s.matches(action="content.published", node_id="n2")
    assert not s.matches(action="media.registered", node_id="n1")
    # "all" watch matches everything
    assert Subscription("s", "bob").matches(action="anything", node_id="zzz")


def test_subscription_scope_and_validation():
    assert Subscription("s", "b").scope == "all"
    assert Subscription("s", "b", node_id="n").scope == "node:n"
    assert Subscription("s", "b", event_prefix="content.").scope == "event:content."
    assert not Subscription("s", "").valid


# --- repository -----------------------------------------------------------


def test_repository_roundtrip(node):
    cms, _ = node
    repo = SqliteSubscriptionRepository(Database(cms.db_path))
    repo.add(Subscription("sub1", "bob", node_id="n1"))
    assert len(repo.for_subscriber("bob")) == 1
    assert repo.find("bob", "n1", "") is not None
    assert [s.subscriber for s in repo.watchers_of("n1")] == ["bob"]
    assert repo.remove("sub1") is True
    assert repo.for_subscriber("bob") == []


# --- command + query: watch + derived inbox ------------------------------


def test_watch_idempotent_and_event(node):
    cms, node_id = node
    fired: list[str] = []
    get_event_bus().subscribe("subscription.created", lambda e: fired.append(e.aggregate_id))
    cmd = SubscriptionCommandService(cms=cms)
    first = cmd.watch(subscriber="bob", node_id=node_id)
    again = cmd.watch(subscriber="bob", node_id=node_id)
    assert first.subscription_id == again.subscription_id  # idempotent
    assert len(fired) == 1


def test_inbox_filters_by_node_and_event_scope(node):
    cms, node_id = node
    cmd = SubscriptionCommandService(cms=cms)
    cmd.watch(subscriber="bob", node_id=node_id)  # watch the page
    cmd.watch(subscriber="carol", event_prefix="content.published")  # watch publishes

    cms.publish_node(node_id, published_by="ed")
    cms.update_node(node_id, name="Doc", slug="doc", payload={"title": "Doc2"}, updated_by="ed")

    q = get_archub_subscription_query_service(cms=cms)
    bob = q.inbox("bob")
    assert bob["watching"] == 1
    assert {i["action"] for i in bob["items"]} >= {"content.published", "content.updated"}

    carol = q.inbox("carol")
    assert {i["action"] for i in carol["items"]} == {"content.published"}

    assert q.inbox("nobody")["total"] == 0


def test_watchers_and_unwatch(node):
    cms, node_id = node
    cmd = SubscriptionCommandService(cms=cms)
    sub = cmd.watch(subscriber="bob", node_id=node_id)
    q = get_archub_subscription_query_service(cms=cms)
    assert q.watchers_of(node_id)["subscribers"] == ["bob"]
    assert cmd.unwatch(sub.subscription_id) is True
    assert q.watchers_of(node_id)["total"] == 0


def test_watch_requires_subscriber(node):
    cms, node_id = node
    with pytest.raises(ValueError):
        SubscriptionCommandService(cms=cms).watch(subscriber="", node_id=node_id)


# --- endpoints ------------------------------------------------------------


def test_subscription_endpoints(tmp_path, monkeypatch):
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
        watched = client.post(
            "/api/platform/subscriptions/watch",
            json={"subscriber": "bob", "node_id": created.node_id},
        )
        assert watched.status_code == 200
        sub_id = watched.json()["subscription_id"]

        cms.publish_node(created.node_id, published_by="ed")

        assert (
            client.get("/api/platform/subscriptions", params={"subscriber": "bob"}).json()["total"]
            == 1
        )
        inbox = client.get("/api/platform/subscriptions/inbox", params={"subscriber": "bob"}).json()
        assert inbox["total"] >= 1
        assert client.get(f"/api/platform/subscriptions/watchers/{created.node_id}").json()[
            "subscribers"
        ] == ["bob"]

        removed = client.delete(f"/api/platform/subscriptions/{sub_id}")
        assert removed.json()["removed"] is True

        bad = client.post("/api/platform/subscriptions/watch", json={"subscriber": ""})
        assert bad.status_code == 422
