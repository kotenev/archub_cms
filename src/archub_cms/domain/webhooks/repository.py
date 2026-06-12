"""Repository port for the webhooks context."""

from __future__ import annotations

__all__ = ["WebhookRepository"]

from typing import Any, Protocol, runtime_checkable

from archub_cms.domain.webhooks.webhook import Webhook, WebhookDeliveryRecord


@runtime_checkable
class WebhookRepository(Protocol):
    def list_webhooks(self, *, active_only: bool = False, limit: int = 100) -> list[Webhook]: ...

    def list_deliveries(self, *, limit: int = 100) -> list[WebhookDeliveryRecord]: ...

    def report(self, *, limit: int = 100) -> dict[str, Any]: ...
