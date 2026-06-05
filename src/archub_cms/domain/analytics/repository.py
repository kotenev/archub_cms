"""Repository port for the analytics context."""

from __future__ import annotations

__all__ = ["AnalyticsRepository"]

from typing import Any, Protocol, runtime_checkable

from archub_cms.domain.analytics.models import ActivityEntry, HealthReport


@runtime_checkable
class AnalyticsRepository(Protocol):
    def health(self) -> HealthReport: ...

    def stats(self) -> dict[str, int]: ...

    def activity(
        self, *, node_id: str = "", action: str = "", actor: str = "", limit: int = 100
    ) -> list[ActivityEntry]: ...

    def audit(self) -> dict[str, Any]: ...

    def cache_report(self, *, limit: int = 20) -> dict[str, Any]: ...
