"""Application service for the edit-locks context.

``LockQueryService`` reports the active lock on a node (with live remaining time).
``LockCommandService`` acquires/releases locks, surfacing a conflict when another
editor already holds an active lock (unless ``force``).
"""

from __future__ import annotations

__all__ = [
    "LockCommandService",
    "LockConflictError",
    "LockQueryService",
    "get_archub_lock_query_service",
]

import time
from typing import Any

from archub_cms.domain.locks.repository import LockRepository
from archub_cms.infrastructure.sqlite.lock_repository import CmsLockRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class LockConflictError(Exception):
    """Raised when a node is already locked by another editor."""


class LockQueryService:
    def __init__(self, repository: LockRepository) -> None:
        self._repo = repository

    def lock(self, node_id: str) -> dict[str, Any] | None:
        found = self._repo.get(node_id)
        return found.as_dict(now=time.time()) if found is not None else None

    def active_locks(self, *, limit: int = 100) -> dict[str, Any]:
        now = time.time()
        items = self._repo.list_active(limit=limit)
        return {"items": [lock.as_dict(now=now) for lock in items], "total": len(items)}


class LockCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: LockRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsLockRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def acquire(
        self,
        node_id: str,
        *,
        owner: str,
        ttl_seconds: float = 1800.0,
        note: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        if not owner.strip():
            raise ValueError("lock owner is required")
        try:
            self._cms.acquire_content_lock(
                node_id, owner=owner, ttl_seconds=ttl_seconds, note=note, force=force
            )
        except ValueError as exc:
            raise LockConflictError(str(exc)) from exc
        # Namespaced distinctly from the legacy activity action "content.locked".
        self._bus.publish(ArcHubDomainEvent("editlock.acquired", node_id, owner, {"forced": force}))
        lock = self._repo.get(node_id)
        assert lock is not None
        return lock.as_dict(now=time.time())

    def release(self, node_id: str, *, owner: str, force: bool = False) -> dict[str, Any]:
        if not owner.strip():
            raise ValueError("lock owner is required")
        try:
            self._cms.release_content_lock(node_id, owner=owner, force=force)
        except ValueError as exc:
            raise LockConflictError(str(exc)) from exc
        self._bus.publish(ArcHubDomainEvent("editlock.released", node_id, owner, {"forced": force}))
        return {"node_id": node_id, "released": True}


def get_archub_lock_query_service(
    *, cms: ArcHubCMSService | None = None, repository: LockRepository | None = None
) -> LockQueryService:
    return LockQueryService(repository or CmsLockRepository(cms))
