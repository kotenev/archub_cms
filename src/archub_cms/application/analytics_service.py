"""Application service for the analytics / health context.

Read-only observability surface: content health (with score/grade), runtime
audit, activity feed, platform stats, delivery-cache report, and a combined
``dashboard`` overview.
"""

from __future__ import annotations

__all__ = ["AnalyticsService", "get_archub_analytics_service"]

from collections import Counter
from typing import Any

from archub_cms.domain.analytics.repository import AnalyticsRepository
from archub_cms.infrastructure.sqlite.analytics_repository import CmsAnalyticsRepository
from archub_cms.services.cms import ArcHubCMSService


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self._repo = repository

    def health(self) -> dict[str, Any]:
        return self._repo.health().as_dict()

    def stats(self) -> dict[str, int]:
        return self._repo.stats()

    def audit(self) -> dict[str, Any]:
        return self._repo.audit()

    def cache(self, *, limit: int = 20) -> dict[str, Any]:
        return self._repo.cache_report(limit=limit)

    def activity(
        self, *, node_id: str = "", action: str = "", actor: str = "", limit: int = 100
    ) -> dict[str, Any]:
        entries = self._repo.activity(node_id=node_id, action=action, actor=actor, limit=limit)
        by_action = Counter(entry.action for entry in entries)
        return {
            "items": [e.as_dict() for e in entries],
            "total": len(entries),
            "by_action": dict(by_action),
        }

    def dashboard(self) -> dict[str, Any]:
        health = self._repo.health()
        recent = self._repo.activity(limit=20)
        return {
            "health": health.as_dict(include_issues=False),
            "stats": self._repo.stats(),
            "recent_activity": [e.as_dict() for e in recent[:10]],
            "activity_by_action": dict(Counter(e.action for e in recent)),
        }


def get_archub_analytics_service(
    *, cms: ArcHubCMSService | None = None, repository: AnalyticsRepository | None = None
) -> AnalyticsService:
    return AnalyticsService(repository or CmsAnalyticsRepository(cms))
