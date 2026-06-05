"""Application service for the webhooks / notifications context (Outbox).

``WebhooksQueryService`` lists webhooks, deliveries and the report.
``WebhooksCommandService`` upserts subscriptions (validating the domain
aggregate, emitting ``webhook.upserted``) and dispatches the outbox in batches —
an injectable ``sender`` keeps it network-free in tests.
"""

from __future__ import annotations

__all__ = [
    "WebhooksCommandService",
    "WebhooksQueryService",
    "get_archub_webhooks_query_service",
]

from collections.abc import Callable, Iterable
from typing import Any

from archub_cms.domain.webhooks.repository import WebhookRepository
from archub_cms.domain.webhooks.webhook import Webhook
from archub_cms.infrastructure.sqlite.webhook_repository import CmsWebhookRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service

WebhookSender = Callable[[str, dict[str, Any], dict[str, str], float], int]


class WebhooksQueryService:
    def __init__(self, repository: WebhookRepository) -> None:
        self._repo = repository

    def webhooks(self, *, active_only: bool = False, limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_webhooks(active_only=active_only, limit=limit)
        return {"items": [w.as_dict() for w in items], "total": len(items)}

    def deliveries(self, *, limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_deliveries(limit=limit)
        return {"items": [d.as_dict() for d in items], "total": len(items)}

    def report(self, *, limit: int = 100) -> dict[str, Any]:
        return self._repo.report(limit=limit)

    def matching(self, event_type: str, *, limit: int = 200) -> dict[str, Any]:
        items = [
            w
            for w in self._repo.list_webhooks(active_only=True, limit=limit)
            if w.subscribes_to(event_type)
        ]
        return {
            "event_type": event_type,
            "items": [w.as_dict() for w in items],
            "total": len(items),
        }


class WebhooksCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: WebhookRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsWebhookRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def upsert_webhook(
        self,
        *,
        name: str,
        target_url: str,
        events: Iterable[str],
        secret: str = "",
        active: bool = True,
        max_attempts: int = 5,
        actor: str,
        webhook_id: str = "",
    ) -> Webhook:
        candidate = Webhook(
            webhook_id=webhook_id,
            name=name,
            target_url=target_url,
            events=tuple(events),
            active=active,
            secret_set=bool(secret),
            max_attempts=max_attempts,
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        stored = self._cms.upsert_webhook(
            name=name,
            target_url=target_url,
            events=list(events),
            secret=secret,
            active=active,
            max_attempts=max_attempts,
            updated_by=actor,
            webhook_id=webhook_id,
        )
        # Distinct from the legacy activity action "webhook.upserted" emitted by
        # cms._record_activity, so subscribers see exactly one domain event.
        self._bus.publish(
            ArcHubDomainEvent(
                "webhook.subscription.upserted",
                stored.webhook_id,
                actor,
                {"events": list(stored.events)},
            )
        )
        return Webhook(
            webhook_id=stored.webhook_id,
            name=stored.name,
            target_url=stored.target_url,
            events=tuple(stored.events),
            active=stored.active,
            secret_set=stored.secret_set,
            timeout_seconds=stored.timeout_seconds,
            max_attempts=stored.max_attempts,
        )

    def dispatch(self, *, limit: int = 50, sender: WebhookSender | None = None) -> dict[str, Any]:
        return self._cms.dispatch_webhook_deliveries(limit=limit, sender=sender)


def get_archub_webhooks_query_service(
    *, cms: ArcHubCMSService | None = None, repository: WebhookRepository | None = None
) -> WebhooksQueryService:
    return WebhooksQueryService(repository or CmsWebhookRepository(cms))
