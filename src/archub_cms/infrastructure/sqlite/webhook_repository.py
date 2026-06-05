"""Webhook repository adapter mapping legacy webhook reads to domain models."""

from __future__ import annotations

__all__ = ["CmsWebhookRepository"]

from typing import Any

from archub_cms.domain.webhooks.webhook import Webhook, WebhookDeliveryRecord
from archub_cms.services.cms import (
    ArcHubCMSService,
    ContentWebhook,
    WebhookDelivery,
    get_archub_cms_service,
)


def _webhook(webhook: ContentWebhook) -> Webhook:
    return Webhook(
        webhook_id=webhook.webhook_id,
        name=webhook.name,
        target_url=webhook.target_url,
        events=tuple(webhook.events),
        active=webhook.active,
        secret_set=webhook.secret_set,
        timeout_seconds=webhook.timeout_seconds,
        max_attempts=webhook.max_attempts,
    )


def _delivery(delivery: WebhookDelivery) -> WebhookDeliveryRecord:
    return WebhookDeliveryRecord(
        delivery_id=delivery.delivery_id,
        webhook_id=delivery.webhook_id,
        event_type=delivery.event_type,
        status=delivery.status,
        target_url=delivery.target_url,
        aggregate_id=delivery.aggregate_id,
    )


class CmsWebhookRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_webhooks(self, *, active_only: bool = False, limit: int = 100) -> list[Webhook]:
        return [_webhook(w) for w in self._cms.list_webhooks(active_only=active_only, limit=limit)]

    def list_deliveries(self, *, limit: int = 100) -> list[WebhookDeliveryRecord]:
        return [_delivery(d) for d in self._cms.list_webhook_deliveries(limit=limit)]

    def report(self, *, limit: int = 100) -> dict[str, Any]:
        return self._cms.webhook_report(limit=limit)
