"""Domain event primitives for ArcHub CMS application services."""

from __future__ import annotations

__all__ = [
    "ArcHubDomainEvent",
    "content_event",
]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArcHubDomainEvent:
    """Small immutable event emitted by application services.

    Events are returned to callers today and documented as the future boundary
    for audit, webhooks, cache invalidation, runtime exports, and integrations.
    """

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
