"""Example plugin: an in-app notifications connector.

Subscribes to collaboration events and builds a per-user notification feed in
memory — demonstrating that the plugin platform reacts to a *new* bounded
context (collaboration) with no changes to the runtime. Like the backlinks
plugin, it never re-enters the write path.

Loaded via ``plugins/example_notifications/plugin.json``.
"""

from __future__ import annotations

__all__ = ["NotificationsPlugin"]

from collections import deque

from archub_cms.domain.collaboration.events import (
    COMMENT_CREATED,
    MENTION_CREATED,
    REACTION_ADDED,
)
from archub_cms.extensibility.extension_points import PluginContext
from archub_cms.kernel.events import ArcHubDomainEvent


class NotificationsPlugin:
    event_types = (COMMENT_CREATED, MENTION_CREATED, REACTION_ADDED)

    def __init__(self, *, capacity: int = 500) -> None:
        self._feed: dict[str, deque[dict]] = {}
        self._capacity = capacity
        self.delivered = 0

    def setup(self, context: PluginContext) -> None:
        context.register(self)

    def handle(self, event: ArcHubDomainEvent) -> None:
        recipient = self._recipient(event)
        if not recipient:
            return
        self.delivered += 1
        feed = self._feed.setdefault(recipient, deque(maxlen=self._capacity))
        feed.appendleft(
            {
                "type": event.event_type,
                "actor": event.actor,
                "node_id": event.metadata.get("node_id", ""),
                "comment_id": event.aggregate_id,
            }
        )

    def notifications_for(self, username: str, *, limit: int = 50) -> list[dict]:
        feed = self._feed.get(username.strip().casefold())
        return list(feed)[:limit] if feed else []

    @staticmethod
    def _recipient(event: ArcHubDomainEvent) -> str:
        if event.event_type == MENTION_CREATED:
            return str(event.metadata.get("mentioned") or "").casefold()
        # For comment/reaction events, notify nobody specific here; mentions
        # carry the targeted fan-out. Returning "" means "no direct recipient".
        return ""
