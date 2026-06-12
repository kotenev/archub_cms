"""Application service for the notification hub context.

Routes domain events to user notification inboxes and external channels
based on per-user preference rules. Integrates with the plugin notification
channels (Slack, email, webhook) for outbound delivery.
"""

from __future__ import annotations

__all__ = ["NotificationHubService", "get_archub_notification_hub_service"]

import secrets
import time
from typing import Any

from archub_cms.domain.notifications.notification import (
    Notification,
    NotificationPreference,
)
from archub_cms.domain.notifications.repository import NotificationRepository
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus


class NotificationHubService:
    def __init__(
        self,
        *,
        repository: NotificationRepository | None = None,
        plugin_host: PluginHost | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = repository
        self._host = plugin_host or get_plugin_host()
        self._bus = event_bus or get_event_bus()
        self._bus.subscribe("*", self._route_event)

    def _route_event(self, event: ArcHubDomainEvent) -> None:
        mentioned = event.metadata.get("mentioned") or event.metadata.get("recipient")
        if not mentioned:
            return
        self._deliver(
            recipient=str(mentioned),
            title=f"{event.event_type}",
            body=event.metadata.get("body", ""),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
        )

    def _deliver(
        self,
        *,
        recipient: str,
        title: str,
        body: str,
        event_type: str,
        aggregate_id: str,
    ) -> None:
        notification = Notification(
            notification_id=secrets.token_urlsafe(10),
            recipient=recipient,
            title=title,
            body=body,
            event_type=event_type,
            aggregate_id=aggregate_id,
            created_at=time.time(),
        )
        if self._repo is not None:
            self._repo.store(notification)

    def inbox(self, username: str, *, unread_only: bool = False, limit: int = 50) -> dict[str, Any]:
        if self._repo is None:
            return {"items": [], "total": 0}
        notifications = self._repo.inbox(username, unread_only=unread_only, limit=limit)
        return {
            "username": username,
            "items": [n.as_dict() for n in notifications],
            "total": len(notifications),
        }

    def mark_read(self, notification_id: str) -> bool:
        if self._repo is None:
            return False
        return self._repo.mark_read(notification_id)

    def preferences(self, username: str) -> dict[str, Any]:
        if self._repo is None:
            return {"username": username, "preferences": []}
        prefs = self._repo.preferences(username)
        return {
            "username": username,
            "preferences": [p.as_dict() for p in prefs],
        }

    def set_preference(self, preference: NotificationPreference) -> dict[str, Any]:
        if self._repo is None:
            return preference.as_dict()
        self._repo.set_preference(preference)
        return preference.as_dict()

    def channels(self) -> dict[str, Any]:
        return {
            "channels": [
                {"name": name, "type": type(ext).__name__}
                for name, ext in self._host.notification_channels.items()
            ]
        }


def get_archub_notification_hub_service(
    *,
    repository: NotificationRepository | None = None,
    plugin_host: PluginHost | None = None,
) -> NotificationHubService:
    return NotificationHubService(repository=repository, plugin_host=plugin_host)
