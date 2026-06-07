"""Activity feed service: chronological activity stream."""

from __future__ import annotations

__all__ = ["ActivityFeedService", "get_archub_activity_feed_service"]

from typing import Any

from archub_cms.domain.activity_feed.models import ActivityEntry
from archub_cms.kernel.events import EventBus


class ActivityFeedService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def record_activity(
        self,
        activity_type: str,
        actor: str,
        target_type: str,
        target_id: str,
        space_key: str = "",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ActivityEntry:
        import time

        from archub_cms.kernel.value_objects import Identity

        return ActivityEntry(
            entry_id=Identity.generate("act-").value,
            activity_type=activity_type,
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            space_key=space_key,
            summary=summary,
            metadata=metadata,
            timestamp=time.time(),
        )

    def list_activities(
        self,
        *,
        space_key: str = "",
        actor: str = "",
        activity_type: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        return {"activities": [], "total": 0}

    def list_user_activities(self, username: str, limit: int = 50) -> dict[str, Any]:
        return {"activities": [], "total": 0}


def get_archub_activity_feed_service(
    event_bus: EventBus | None = None,
) -> ActivityFeedService:
    return ActivityFeedService(event_bus=event_bus)
