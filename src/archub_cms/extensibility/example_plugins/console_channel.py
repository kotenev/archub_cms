"""Example plugin: an outbound notification channel (NotificationExt).

Demonstrates the channel seam that Slack/email/webhook integrations plug into.
The host auto-subscribes every channel to the event bus, so all domain events
fan out here. This channel records them to an in-memory ring buffer (and logs);
a real channel would POST to Slack or send email.
"""

from __future__ import annotations

__all__ = ["ConsoleChannelPlugin"]

import logging
from collections import deque

from archub_cms.extensibility.extension_points import PluginContext
from archub_cms.kernel.events import ArcHubDomainEvent

logger = logging.getLogger("archub_cms.plugins.console_channel")


class ConsoleChannelPlugin:
    channel = "console"

    def __init__(self, *, capacity: int = 200) -> None:
        self._sent: deque[dict] = deque(maxlen=capacity)

    def setup(self, context: PluginContext) -> None:
        context.register(self)

    def notify(self, event: ArcHubDomainEvent) -> None:
        record = {
            "channel": self.channel,
            "event_type": event.event_type,
            "actor": event.actor,
            "aggregate_id": event.aggregate_id,
        }
        self._sent.append(record)
        logger.debug("console notification: %s", record)

    def sent(self, limit: int = 50) -> list[dict]:
        return list(self._sent)[-limit:][::-1]

    @property
    def delivered(self) -> int:
        return len(self._sent)
