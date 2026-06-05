"""Analytics repository adapter mapping legacy reports to domain read models."""

from __future__ import annotations

__all__ = ["CmsAnalyticsRepository"]

from typing import Any

from archub_cms.domain.analytics.models import ActivityEntry, HealthReport
from archub_cms.services.cms import ArcHubCMSService, ContentActivity, get_archub_cms_service


def _activity(activity: ContentActivity) -> ActivityEntry:
    return ActivityEntry(
        action=activity.action,
        actor=activity.actor,
        summary=activity.summary,
        node_id=activity.node_id,
        node_name=activity.node_name,
        occurred_at=activity.created_at,
        metadata=dict(activity.metadata),
    )


class CmsAnalyticsRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def health(self) -> HealthReport:
        return HealthReport.from_result(self._cms.content_health_report())

    def stats(self) -> dict[str, int]:
        return self._cms.stats()

    def activity(
        self, *, node_id: str = "", action: str = "", actor: str = "", limit: int = 100
    ) -> list[ActivityEntry]:
        return [
            _activity(a)
            for a in self._cms.list_activity(
                node_id=node_id, action=action, actor=actor, limit=limit
            )
        ]

    def audit(self) -> dict[str, Any]:
        return self._cms.runtime_audit_report()

    def cache_report(self, *, limit: int = 20) -> dict[str, Any]:
        return self._cms.delivery_cache_report(limit=limit)
