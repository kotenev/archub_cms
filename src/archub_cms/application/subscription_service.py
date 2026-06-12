"""Application service for subscriptions/watchers + derived activity inbox.

``SubscriptionCommandService`` persists watches (idempotent) and emits events.
``SubscriptionQueryService`` lists a subscriber's watches, a node's watchers,
and computes the **inbox** — the activity-log entries matching a subscriber's
watches — without writing anything on the event path.
"""

from __future__ import annotations

__all__ = [
    "SubscriptionCommandService",
    "SubscriptionQueryService",
    "get_archub_subscription_query_service",
]

import secrets
import time
from typing import Any

from archub_cms.domain.subscriptions.repository import SubscriptionRepository
from archub_cms.domain.subscriptions.subscription import Subscription
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.subscription_repository import SqliteSubscriptionRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


def _repo(
    cms: ArcHubCMSService, repository: SubscriptionRepository | None
) -> SubscriptionRepository:
    return repository or SqliteSubscriptionRepository(Database(cms.db_path))


class SubscriptionCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: SubscriptionRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = _repo(self._cms, repository)
        self._bus = event_bus or get_event_bus()

    def watch(self, *, subscriber: str, node_id: str = "", event_prefix: str = "") -> Subscription:
        candidate = Subscription(
            subscription_id="",
            subscriber=subscriber,
            node_id=node_id.strip(),
            event_prefix=event_prefix.strip(),
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        existing = self._repo.find(subscriber, node_id.strip(), event_prefix.strip())
        if existing is not None:
            return existing

        subscription = Subscription(
            subscription_id=secrets.token_urlsafe(10),
            subscriber=subscriber,
            node_id=node_id.strip(),
            event_prefix=event_prefix.strip(),
            created_at=time.time(),
        )
        self._repo.add(subscription)
        self._bus.publish(
            ArcHubDomainEvent(
                "subscription.created",
                subscription.subscription_id,
                subscriber,
                {"scope": subscription.scope},
            )
        )
        return subscription

    def unwatch(self, subscription_id: str, *, actor: str = "") -> bool:
        removed = self._repo.remove(subscription_id)
        if removed:
            self._bus.publish(ArcHubDomainEvent("subscription.removed", subscription_id, actor, {}))
        return removed


class SubscriptionQueryService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: SubscriptionRepository | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = _repo(self._cms, repository)

    def subscriptions_for(self, subscriber: str) -> dict[str, Any]:
        items = self._repo.for_subscriber(subscriber)
        return {
            "subscriber": subscriber,
            "items": [s.as_dict() for s in items],
            "total": len(items),
        }

    def watchers_of(self, node_id: str) -> dict[str, Any]:
        items = self._repo.watchers_of(node_id)
        return {
            "node_id": node_id,
            "subscribers": sorted({s.subscriber for s in items}),
            "total": len(items),
        }

    def inbox(self, subscriber: str, *, limit: int = 50) -> dict[str, Any]:
        subscriptions = self._repo.for_subscriber(subscriber)
        if not subscriptions:
            return {"subscriber": subscriber, "items": [], "total": 0, "watching": 0}
        activities = self._cms.list_activity(limit=max(limit * 4, 100))
        items: list[dict[str, Any]] = []
        for activity in activities:
            if any(
                sub.matches(action=activity.action, node_id=activity.node_id)
                for sub in subscriptions
            ):
                items.append(
                    {
                        "action": activity.action,
                        "actor": activity.actor,
                        "summary": activity.summary,
                        "node_id": activity.node_id,
                        "node_name": activity.node_name,
                        "route_path": activity.route_path,
                        "occurred_at": activity.created_at,
                    }
                )
            if len(items) >= limit:
                break
        return {
            "subscriber": subscriber,
            "items": items,
            "total": len(items),
            "watching": len(subscriptions),
        }


def get_archub_subscription_query_service(
    *, cms: ArcHubCMSService | None = None, repository: SubscriptionRepository | None = None
) -> SubscriptionQueryService:
    return SubscriptionQueryService(cms=cms, repository=repository)
