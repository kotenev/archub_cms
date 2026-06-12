"""The ``Webhook`` aggregate and ``WebhookDeliveryRecord`` read model."""

from __future__ import annotations

__all__ = ["Webhook", "WebhookDeliveryRecord"]

from dataclasses import dataclass, field
from typing import Any


def _event_matches(subscription: str, event_type: str) -> bool:
    if subscription == "*":
        return True
    if subscription.endswith("*"):
        return event_type.startswith(subscription[:-1])
    return subscription == event_type


@dataclass(frozen=True)
class Webhook:
    """An outbound webhook subscription."""

    webhook_id: str
    name: str
    target_url: str
    events: tuple[str, ...] = ()
    active: bool = True
    secret_set: bool = False
    timeout_seconds: float = 5.0
    max_attempts: int = 5

    def subscribes_to(self, event_type: str) -> bool:
        return self.active and any(_event_matches(sub, event_type) for sub in self.events)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("webhook name is required")
        if not self.target_url.strip():
            errors.append("webhook target_url is required")
        elif not self.target_url.startswith(("http://", "https://")):
            errors.append("webhook target_url must be http(s)")
        if not self.events:
            errors.append("webhook must subscribe to at least one event")
        if self.max_attempts < 1:
            errors.append("max_attempts must be >= 1")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "name": self.name,
            "target_url": self.target_url,
            "events": list(self.events),
            "active": self.active,
            "secret_set": self.secret_set,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
        }


@dataclass(frozen=True)
class WebhookDeliveryRecord:
    """A single outbox delivery attempt projection."""

    delivery_id: int
    webhook_id: str
    event_type: str
    status: str
    target_url: str = ""
    aggregate_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "webhook_id": self.webhook_id,
            "event_type": self.event_type,
            "status": self.status,
            "target_url": self.target_url,
            "aggregate_id": self.aggregate_id,
            "metadata": dict(self.metadata),
        }
