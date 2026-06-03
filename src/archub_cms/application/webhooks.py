"""Webhook integration application service for ArcHub CMS."""

from __future__ import annotations

__all__ = [
    "WebhookOperationResult",
    "ArcHubWebhookService",
    "get_archub_webhook_service",
]

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service

WebhookSender = Callable[[str, dict[str, Any], dict[str, str], float], int]


@dataclass(frozen=True)
class WebhookOperationResult:
    """Result envelope for webhook management and dispatch use cases."""

    payload: dict[str, Any]
    events: tuple[ArcHubDomainEvent, ...] = ()
    status_code: int = 200

    @property
    def ok(self) -> bool:
        return bool(self.payload.get("ok", True))

    def as_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        if not include_events:
            return self.payload
        return {
            **self.payload,
            "events": [event.as_dict() for event in self.events],
        }


class ArcHubWebhookService:
    """Application boundary for webhook subscriptions, deliveries, and retry dispatch."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def subscriptions(self, *, active_only: bool = False, limit: int = 100) -> dict[str, Any]:
        items = self._cms.list_webhooks(active_only=active_only, limit=limit)
        return {"items": [item.__dict__ for item in items], "total": len(items)}

    def deliveries(
        self,
        *,
        status: str = "",
        webhook_id: str = "",
        event_type: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        items = self._cms.list_webhook_deliveries(
            status=status,
            webhook_id=webhook_id,
            event_type=event_type,
            limit=limit,
        )
        return {"items": [item.__dict__ for item in items], "total": len(items)}

    def report(self, *, limit: int = 100) -> dict[str, Any]:
        return self._cms.webhook_report(limit=limit)

    def upsert(
        self,
        *,
        name: str,
        target_url: str,
        events: Iterable[str],
        secret: str = "",
        active: bool = True,
        timeout_seconds: float = 5.0,
        max_attempts: int = 5,
        actor: str,
        webhook_id: str = "",
    ) -> WebhookOperationResult:
        webhook = self._cms.upsert_webhook(
            webhook_id=webhook_id,
            name=name,
            target_url=target_url,
            events=events,
            secret=secret,
            active=active,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            updated_by=actor,
        )
        return WebhookOperationResult(
            payload=webhook.__dict__,
            events=(
                ArcHubDomainEvent(
                    event_type="webhook.subscription.upserted",
                    aggregate_id=webhook.webhook_id,
                    actor=actor,
                    metadata={
                        "name": webhook.name,
                        "target_url": webhook.target_url,
                        "events": list(webhook.events),
                        "active": webhook.active,
                    },
                ),
            ),
        )

    def dispatch_pending(
        self,
        *,
        limit: int = 50,
        actor: str = "system",
        sender: WebhookSender | None = None,
    ) -> WebhookOperationResult:
        result = self._cms.dispatch_webhook_deliveries(limit=limit, sender=sender)
        return WebhookOperationResult(
            payload=result,
            events=(
                ArcHubDomainEvent(
                    event_type="webhook.dispatch.completed",
                    aggregate_id="webhook-deliveries",
                    actor=actor,
                    metadata={
                        "processed_count": result.get("processed_count", 0),
                        "delivered": len(result.get("delivered", [])),
                        "retry": len(result.get("retry", [])),
                        "failed": len(result.get("failed", [])),
                    },
                ),
            ),
        )


def get_archub_webhook_service(cms: ArcHubCMSService | None = None) -> ArcHubWebhookService:
    return ArcHubWebhookService(cms=cms)
