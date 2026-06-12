"""Notification repository port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from archub_cms.domain.notifications.notification import (
    Notification,
    NotificationPreference,
)


@runtime_checkable
class NotificationRepository(Protocol):
    def store(self, notification: Notification) -> Notification: ...
    def mark_read(self, notification_id: str) -> bool: ...
    def inbox(
        self, username: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]: ...
    def preferences(self, username: str) -> list[NotificationPreference]: ...
    def set_preference(self, preference: NotificationPreference) -> NotificationPreference: ...
