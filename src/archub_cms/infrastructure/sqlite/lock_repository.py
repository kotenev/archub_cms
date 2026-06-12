"""Lock repository adapter mapping legacy content locks to the aggregate."""

from __future__ import annotations

__all__ = ["CmsLockRepository"]

from archub_cms.domain.locks.lock import EditLock
from archub_cms.services.cms import ArcHubCMSService, ContentLock, get_archub_cms_service


def _lock(lock: ContentLock) -> EditLock:
    return EditLock(
        node_id=lock.node_id,
        owner=lock.owner,
        token=lock.token,
        note=lock.note,
        acquired_at=lock.acquired_at,
        expires_at=lock.expires_at,
        node_name=lock.node_name,
        route_path=lock.route_path,
    )


class CmsLockRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def get(self, node_id: str) -> EditLock | None:
        found = self._cms.get_content_lock(node_id)
        return _lock(found) if found is not None else None

    def list_active(self, *, limit: int = 100) -> list[EditLock]:
        return [_lock(item) for item in self._cms.list_content_locks(active_only=True, limit=limit)]
