"""The ``Subscription`` aggregate (a watch on a node and/or event prefix)."""

from __future__ import annotations

__all__ = ["Subscription"]

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Subscription:
    """A subscriber's watch. Empty ``node_id``/``event_prefix`` means "any"."""

    subscription_id: str
    subscriber: str
    node_id: str = ""
    event_prefix: str = ""
    created_at: float = 0.0

    @property
    def scope(self) -> str:
        if self.node_id and self.event_prefix:
            return f"node:{self.node_id}+event:{self.event_prefix}"
        if self.node_id:
            return f"node:{self.node_id}"
        if self.event_prefix:
            return f"event:{self.event_prefix}"
        return "all"

    def matches(self, *, action: str, node_id: str) -> bool:
        if self.node_id and self.node_id != node_id:
            return False
        return not self.event_prefix or action.startswith(self.event_prefix)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.subscriber.strip():
            errors.append("subscriber is required")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "subscriber": self.subscriber,
            "node_id": self.node_id,
            "event_prefix": self.event_prefix,
            "scope": self.scope,
            "created_at": self.created_at,
        }
