"""Notification hub bounded context: centralized notification routing.

Manages user notification preferences, delivery channels (email, Slack,
webhook, in-app), and notification templates. Incoming domain events are
routed through user preference rules and delivered via the appropriate
channel plugins.
"""

from __future__ import annotations

from archub_cms.domain.notifications.channel import (
    ChannelType,
    NotificationChannel,
)
from archub_cms.domain.notifications.notification import (
    Notification,
    NotificationPreference,
)
from archub_cms.domain.notifications.repository import NotificationRepository

__all__ = [
    "ChannelType",
    "Notification",
    "NotificationChannel",
    "NotificationPreference",
    "NotificationRepository",
]
