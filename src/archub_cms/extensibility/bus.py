"""Bridge between the kernel EventBus and plugin observability.

``HookLog`` subscribes to every event and keeps a bounded record of what fired,
so the host can report "the content.published hook ran" without plugins needing
to expose internals.
"""

from __future__ import annotations

__all__ = ["HookLog"]

from collections import deque
from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent, EventBus


class HookLog:
    def __init__(self, event_bus: EventBus, *, capacity: int = 200) -> None:
        self._events: deque[ArcHubDomainEvent] = deque(maxlen=capacity)
        self._counts: dict[str, int] = {}
        event_bus.subscribe("*", self._record)

    def _record(self, event: ArcHubDomainEvent) -> None:
        self._events.append(event)
        self._counts[event.event_type] = self._counts.get(event.event_type, 0) + 1

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        items = list(self._events)[-limit:]
        return [event.as_dict() for event in reversed(items)]
