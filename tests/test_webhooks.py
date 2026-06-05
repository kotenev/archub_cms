"""Tests for the webhooks / notifications context (Phase 16)."""

from __future__ import annotations

import pytest

from archub_cms.application.webhooks_service import (
    WebhooksCommandService,
    get_archub_webhooks_query_service,
)
from archub_cms.domain.webhooks.webhook import Webhook
from archub_cms.extensibility.example_plugins.console_channel import ConsoleChannelPlugin
from archub_cms.extensibility.host import PluginHost
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


# --- domain: subscription matching + validation --------------------------


def test_webhook_subscription_matching():
    w = Webhook("w", "n", "https://x", events=("content.*", "media.registered"))
    assert w.subscribes_to("content.published")
    assert w.subscribes_to("media.registered")
    assert not w.subscribes_to("workflow.transitioned")
    assert Webhook("w", "n", "https://x", events=("*",)).subscribes_to("anything")
    assert not Webhook("w", "n", "https://x", events=("content.*",), active=False).subscribes_to(
        "content.published"
    )


def test_webhook_validation():
    assert Webhook("w", "CI", "https://x", events=("content.*",)).valid
    errors = Webhook("w", "", "ftp://x", events=(), max_attempts=0).validate()
    assert len(errors) == 4  # name, url scheme, events, max_attempts


# --- command + query services --------------------------------------------


def test_upsert_emits_single_event_and_lists(cms):
    fired: list[str] = []
    get_event_bus().subscribe(
        "webhook.subscription.upserted", lambda e: fired.append(e.aggregate_id)
    )
    cmd = WebhooksCommandService(cms=cms)
    hook = cmd.upsert_webhook(
        name="CI", target_url="https://ci/hook", events=["content.published"], secret="s", actor="a"
    )
    assert hook.secret_set
    assert fired == [hook.webhook_id]  # exactly one (no legacy collision)

    q = get_archub_webhooks_query_service(cms=cms)
    assert q.webhooks()["total"] == 1
    assert q.matching("content.published")["total"] == 1
    assert q.matching("workflow.x")["total"] == 0


def test_upsert_rejects_invalid(cms):
    cmd = WebhooksCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.upsert_webhook(name="", target_url="ftp://x", events=[], actor="a")


def test_outbox_dispatch_with_stub_sender(cms):
    cmd = WebhooksCommandService(cms=cms)
    cmd.upsert_webhook(
        name="CI", target_url="https://ci/hook", events=["content.published"], actor="a"
    )
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Doc",
        slug="doc",
        payload={"title": "Doc"},
        created_by="t",
    )
    cms.publish_node(node.node_id, published_by="t")

    q = get_archub_webhooks_query_service(cms=cms)
    assert q.deliveries()["total"] >= 1  # enqueued in the outbox on publish

    calls: list[str] = []

    def sender(url, payload, headers, timeout):
        calls.append(url)
        return 200

    result = cmd.dispatch(limit=50, sender=sender)
    assert "delivered" in result and "processed_count" in result
    assert calls == ["https://ci/hook"]


# --- NotificationExt channel ---------------------------------------------


def test_notification_channel_receives_events(cms):
    host = PluginHost().load()
    assert "console" in host.report()["notification_channels"]
    channel = host.notification_channels["console"]
    assert isinstance(channel, ConsoleChannelPlugin)

    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="N",
        slug="n",
        payload={"title": "N"},
        created_by="t",
    )
    cms.publish_node(node.node_id, published_by="t")

    assert channel.delivered >= 2  # content.created + content.published
    assert any(rec["event_type"] == "content.published" for rec in channel.sent())


# --- endpoints ------------------------------------------------------------


def test_webhooks_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        created = client.post(
            "/api/platform/webhooks",
            json={
                "name": "CI",
                "target_url": "https://ci/hook",
                "events": ["content.*"],
                "actor": "a",
            },
        )
        assert created.status_code == 200
        assert created.json()["events"] == ["content.*"]

        assert client.get("/api/platform/webhooks").json()["total"] == 1
        assert (
            client.get(
                "/api/platform/webhooks/matching", params={"event_type": "content.published"}
            ).json()["total"]
            == 1
        )

        channels = client.get("/api/platform/notifications/channels").json()
        assert "console" in channels["channels"]

        bad = client.post("/api/platform/webhooks", json={"name": "", "target_url": "ftp://x"})
        assert bad.status_code == 422
