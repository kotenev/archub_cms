"""Application service for the audit trail context.

Records every domain event as an immutable audit entry and supports
querying by aggregate, actor, action, and time range.
"""

from __future__ import annotations

__all__ = ["AuditTrailService", "get_archub_audit_trail_service"]

import secrets
import time
from typing import Any

from archub_cms.domain.audit_trail.entry import AuditEntry, AuditQuery
from archub_cms.domain.audit_trail.repository import AuditTrailRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus


class AuditTrailService:
    def __init__(
        self,
        *,
        repository: AuditTrailRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = repository
        self._bus = event_bus or get_event_bus()
        self._bus.subscribe("*", self._on_event)

    def _on_event(self, event: ArcHubDomainEvent) -> None:
        if self._repo is None:
            return
        entry = AuditEntry(
            entry_id=secrets.token_urlsafe(12),
            action=event.event_type,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.metadata.get("aggregate_type", ""),
            actor=event.actor,
            timestamp=time.time(),
            metadata=event.metadata,
        )
        self._repo.record(entry)

    def query(self, query: AuditQuery | None = None) -> dict[str, Any]:
        if self._repo is None:
            return {"items": [], "total": 0}
        q = query or AuditQuery()
        entries = self._repo.query(q)
        return {
            "items": [entry.as_dict() for entry in entries],
            "total": len(entries),
        }

    def for_aggregate(self, aggregate_id: str, *, limit: int = 50) -> dict[str, Any]:
        return self.query(AuditQuery(aggregate_id=aggregate_id, limit=limit))

    def for_actor(self, actor: str, *, limit: int = 50) -> dict[str, Any]:
        return self.query(AuditQuery(actor=actor, limit=limit))


def get_archub_audit_trail_service(
    *,
    repository: AuditTrailRepository | None = None,
) -> AuditTrailService:
    return AuditTrailService(repository=repository)
