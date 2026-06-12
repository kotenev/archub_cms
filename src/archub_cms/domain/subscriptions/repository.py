"""Repository port for the subscriptions context."""

from __future__ import annotations

__all__ = ["SubscriptionRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.subscriptions.subscription import Subscription


@runtime_checkable
class SubscriptionRepository(Protocol):
    def add(self, subscription: Subscription) -> None: ...

    def remove(self, subscription_id: str) -> bool: ...

    def for_subscriber(self, subscriber: str) -> list[Subscription]: ...

    def watchers_of(self, node_id: str) -> list[Subscription]: ...

    def find(self, subscriber: str, node_id: str, event_prefix: str) -> Subscription | None: ...
