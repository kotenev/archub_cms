"""Domain events and a synchronous in-process event bus.

``ArcHubDomainEvent`` is the canonical event type (the original lived in
``archub_cms.domain.events`` and is re-exported there for back-compat). The
``EventBus`` lets application services publish events that plugins, webhooks,
audit sinks, cache invalidation, and runtime exports subscribe to — the
extension seam the docstring in the old ``domain/events.py`` promised.
"""

from __future__ import annotations

__all__ = [
    "ArcHubDomainEvent",
    "EventBus",
    "EventHandler",
    "content_event",
    "get_event_bus",
]

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("archub_cms.events")

EventHandler = Callable[["ArcHubDomainEvent"], None]


@dataclass(frozen=True)
class ArcHubDomainEvent:
    """Small immutable event emitted by application services."""

    event_type: str
    aggregate_id: str
    actor: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "actor": self.actor,
            "metadata": dict(self.metadata),
        }


def content_event(
    event_type: str,
    *,
    node_id: str,
    actor: str,
    metadata: dict[str, Any] | None = None,
) -> ArcHubDomainEvent:
    return ArcHubDomainEvent(
        event_type=event_type,
        aggregate_id=node_id,
        actor=actor,
        metadata=metadata or {},
    )


class EventBus:
    """Synchronous in-process pub/sub for domain events.

    Subscriptions are keyed by exact ``event_type`` or the ``"*"`` wildcard.
    Handlers are isolated: a failing handler is logged and never breaks the
    publisher or other subscribers (events must not corrupt the write path).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        key = event_type or "*"
        self._handlers.setdefault(key, []).append(handler)

        def unsubscribe() -> None:
            handlers = self._handlers.get(key)
            if handlers and handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def publish(self, event: ArcHubDomainEvent) -> None:
        for key in (event.event_type, "*"):
            for handler in tuple(self._handlers.get(key, ())):
                try:
                    handler(event)
                except Exception:  # subscribers must not break publishers
                    logger.exception("event handler failed for %s", event.event_type)

    def publish_many(self, events: object) -> None:
        for event in events or ():
            if isinstance(event, ArcHubDomainEvent):
                self.publish(event)

    def clear(self) -> None:
        self._handlers.clear()


_DEFAULT_BUS = EventBus()


def get_event_bus() -> EventBus:
    """Return the process-wide default event bus."""
    return _DEFAULT_BUS
