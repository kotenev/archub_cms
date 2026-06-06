"""Notification channel value objects."""

from __future__ import annotations

__all__ = ["ChannelType", "NotificationChannel"]

from dataclasses import dataclass
from typing import Any


class ChannelType:
    IN_APP = "in_app"
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"


@dataclass(frozen=True)
class NotificationChannel:
    """Descriptor for a notification delivery channel."""

    name: str
    channel_type: str
    config: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "channel_type": self.channel_type,
            "config": self.config or {},
        }
