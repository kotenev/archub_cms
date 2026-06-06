"""AggregateRoot base class: standardized identity, event collection, and versioning.

Every DDD aggregate root inherits from ``AggregateRoot`` to get:
- an ``aggregate_id`` (string identity)
- a ``version`` counter for optimistic concurrency
- a ``collect_events()`` protocol that the UnitOfWork calls after commit
- a ``load_from_history()`` class method for event-sourced reconstitution
"""

from __future__ import annotations

__all__ = ["AggregateRoot"]

from abc import ABC, abstractmethod
from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent


class AggregateRoot(ABC):
    """Base class for all DDD aggregate roots.

    Subclasses define domain behavior as methods that mutate internal state
    and call ``_record_event()``. The infrastructure reads pending events via
    ``collect_events()`` after a successful transaction.
    """

    def __init__(self, aggregate_id: str, *, version: int = 0) -> None:
        self.aggregate_id = aggregate_id
        self.version = version
        self._pending_events: list[ArcHubDomainEvent] = []

    def _record_event(self, event: ArcHubDomainEvent) -> None:
        self._pending_events.append(event)
        self.version += 1

    def collect_events(self) -> list[ArcHubDomainEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    @property
    def has_pending_events(self) -> bool:
        return bool(self._pending_events)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AggregateRoot):
            return NotImplemented
        return type(self) is type(other) and self.aggregate_id == other.aggregate_id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.aggregate_id))

    @classmethod
    @abstractmethod
    def reconstitute(cls, aggregate_id: str, state: dict[str, Any]) -> AggregateRoot:
        """Rebuild an aggregate from persisted state (event-sourcing / snapshot)."""
