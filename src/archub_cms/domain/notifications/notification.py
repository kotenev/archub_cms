"""Notification and NotificationPreference domain models."""

from __future__ import annotations

__all__ = ["Notification", "NotificationPreference"]

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Notification:
    """A notification addressed to a user through a channel."""

    notification_id: str
    recipient: str
    title: str
    body: str
    channel: str = "in_app"
    event_type: str = ""
    aggregate_id: str = ""
    read: bool = False
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_read(self) -> None:
        self.read = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "recipient": self.recipient,
            "title": self.title,
            "body": self.body,
            "channel": self.channel,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "read": self.read,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NotificationPreference:
    """Per-user notification routing preference for an event type."""

    username: str
    event_type: str
    channels: tuple[str, ...] = ("in_app",)
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "event_type": self.event_type,
            "channels": list(self.channels),
            "enabled": self.enabled,
        }
